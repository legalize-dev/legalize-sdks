"""Read-only integration tests — exercise every GET endpoint against prod.

These assert the *contract*, not specific row counts that will drift
over time. We check types, required fields, and structural invariants
that must hold for the life of the API.

Countries chosen because they're guaranteed stable:
- ``es`` (Spain) has ~12K laws, multiple law types, jurisdictions → covers the long tail
- ``fr`` (France) has many laws → pagination stress
"""

from __future__ import annotations

import pytest

from legalize import (
    InvalidRequestError,
    Legalize,
    NotFoundError,
)
from legalize.models import (
    CommitsResponse,
    CountryInfo,
    JurisdictionInfo,
    LawAtCommitResponse,
    LawDetail,
    LawMeta,
    PaginatedLaws,
    ReformsResponse,
    StatsResponse,
)


# ---- top-level lookups ------------------------------------------------


class TestCountries:
    def test_list_has_core_countries(self, client: Legalize):
        countries = client.countries.list()
        assert len(countries) > 0
        codes = {c.country for c in countries}
        # ES must always be there — it's the flagship.
        assert "es" in codes
        # All entries are typed
        assert all(isinstance(c, CountryInfo) for c in countries)
        # Counts are non-negative
        assert all(c.count >= 0 for c in countries)


class TestJurisdictions:
    def test_spain_has_jurisdictions(self, client: Legalize):
        regions = client.jurisdictions.list("es")
        assert len(regions) > 0
        assert all(isinstance(r, JurisdictionInfo) for r in regions)

    def test_unknown_country_404(self, client: Legalize):
        with pytest.raises(NotFoundError):
            client.jurisdictions.list("zz")


class TestLawTypes:
    def test_spain(self, client: Legalize):
        types = client.law_types.list("es")
        assert len(types) > 0
        # Spain always has at least the Constitution and leyes
        assert "constitucion" in types or "constitución" in types or "ley" in types

    def test_unknown_country_404(self, client: Legalize):
        with pytest.raises(NotFoundError):
            client.law_types.list("zz")


# ---- laws: list / search / retrieve -----------------------------------


class TestLawsList:
    def test_first_page(self, client: Legalize):
        page = client.laws.list("es", page=1, per_page=10)
        assert isinstance(page, PaginatedLaws)
        assert page.country == "es"
        assert page.page == 1
        assert page.per_page == 10
        assert page.total > 0
        assert len(page.results) <= 10
        # All results share the country
        assert all(law.country == "es" for law in page.results)

    def test_filters_by_law_type(self, client: Legalize):
        page = client.laws.list("es", law_type="constitucion", per_page=5)
        # May be empty if the type doesn't exist, otherwise all must match.
        for law in page.results:
            assert law.law_type == "constitucion"

    def test_filters_by_year(self, client: Legalize):
        page = client.laws.list("es", year=2018, per_page=5)
        for law in page.results:
            if law.publication_date:
                assert law.publication_date.startswith("2018")

    def test_status_filter(self, client: Legalize):
        page = client.laws.list("es", status="vigente", per_page=5)
        for law in page.results:
            # status is nullable — only check when present
            if law.status:
                assert law.status == "vigente"

    def test_invalid_year_rejected(self, client: Legalize):
        with pytest.raises(InvalidRequestError):
            client.laws.list("es", year=99)  # 2-digit year not accepted

    def test_invalid_country_404(self, client: Legalize):
        with pytest.raises(NotFoundError):
            client.laws.list("zz")


class TestLawsSearch:
    def test_basic_search(self, client: Legalize):
        page = client.laws.search("es", q="protección de datos", per_page=5)
        assert page.query == "protección de datos"
        # Spain should have matches for this common query
        assert page.total > 0
        assert len(page.results) > 0

    def test_empty_q_rejected_client_side(self, client: Legalize):
        # The SDK rejects empty q before touching the network
        with pytest.raises(ValueError, match="q"):
            client.laws.search("es", q="")

    def test_search_respects_filters(self, client: Legalize):
        page = client.laws.search("es", q="ley", law_type="ley_organica", per_page=5)
        for law in page.results:
            assert law.law_type == "ley_organica"


class TestLawsRetrieve:
    # A law that's extremely unlikely to be deleted: Spain's Constitution.
    # We look up its real ID dynamically so the test survives ID rewrites.

    @pytest.fixture(scope="class")
    def stable_law_id(self, api_key, base_url):
        client = Legalize(api_key=api_key, base_url=base_url)
        try:
            page = client.laws.list("es", law_type="constitucion", per_page=1)
            if not page.results:
                pytest.skip("no constitucion found — dataset shape changed")
            return page.results[0].id
        finally:
            client.close()

    def test_meta(self, client: Legalize, stable_law_id: str):
        meta = client.laws.meta("es", stable_law_id)
        assert isinstance(meta, LawMeta)
        assert meta.id == stable_law_id
        assert meta.country == "es"
        assert meta.title

    def test_retrieve_has_content(self, client: Legalize, stable_law_id: str):
        law = client.laws.retrieve("es", stable_law_id)
        assert isinstance(law, LawDetail)
        assert law.id == stable_law_id
        # content_md can be None if GitHub fetch fails, but for the
        # Constitution it's always populated.
        assert law.content_md, "constitucion should always have content"
        assert len(law.content_md) > 100

    def test_retrieve_404(self, client: Legalize):
        with pytest.raises(NotFoundError):
            client.laws.retrieve("es", "does_not_exist_xxxxx")


# ---- laws: history (commits, reforms, time-travel) --------------------


class TestLawHistory:
    @pytest.fixture(scope="class")
    def reformed_law(self, api_key, base_url):
        """A law with ≥1 reform so history tests have something to verify."""
        client = Legalize(api_key=api_key, base_url=base_url)
        try:
            # Grab a recent law that's likely to have reforms.
            page = client.laws.list("es", per_page=20, sort="date_desc")
            for law in page.results:
                reforms = client.reforms.list("es", law.id, limit=1)
                if reforms.total > 0:
                    return law.id
            pytest.skip("no reformed law found in first 20 — unusual")
        finally:
            client.close()

    def test_commits(self, client: Legalize, reformed_law: str):
        resp = client.laws.commits("es", reformed_law)
        assert isinstance(resp, CommitsResponse)
        assert resp.law_id == reformed_law
        assert len(resp.commits) >= 1
        # SHAs are hex
        for commit in resp.commits:
            assert len(commit.sha) >= 7
            int(commit.sha, 16)  # raises if not hex

    def test_at_commit(self, client: Legalize, reformed_law: str):
        commits = client.laws.commits("es", reformed_law)
        sha = commits.commits[-1].sha  # oldest
        snapshot = client.laws.at_commit("es", reformed_law, sha)
        assert isinstance(snapshot, LawAtCommitResponse)
        assert snapshot.sha == sha
        # Content at an old commit may be empty in edge cases, but the
        # shape must be right.
        assert isinstance(snapshot.content_md, str)

    def test_reforms_list(self, client: Legalize, reformed_law: str):
        resp = client.reforms.list("es", reformed_law, limit=10)
        assert isinstance(resp, ReformsResponse)
        assert resp.law_id == reformed_law
        assert resp.total >= 1
        assert all(r.date for r in resp.reforms)

    def test_reforms_iter_matches_total(self, client: Legalize, reformed_law: str):
        total = client.reforms.list("es", reformed_law, limit=1).total
        collected = list(client.reforms.iter("es", reformed_law, batch=50))
        assert len(collected) == total

    def test_invalid_sha_rejected(self, client: Legalize, reformed_law: str):
        with pytest.raises(InvalidRequestError):
            client.laws.at_commit("es", reformed_law, "nothex!")


# ---- stats ------------------------------------------------------------


class TestStats:
    def test_spain_stats(self, client: Legalize):
        stats = client.stats.retrieve("es")
        assert isinstance(stats, StatsResponse)
        assert stats.country == "es"
        assert len(stats.law_types) > 0
        # Activity rows are plain dicts (spec has dict[str, Any])
        for row in stats.reform_activity_by_year:
            assert "year" in row or "count" in row  # loose — keys can vary


# ---- pagination end-to-end -------------------------------------------


class TestPaginationLive:
    def test_iter_limit_caps(self, client: Legalize):
        collected = list(client.laws.iter("es", per_page=50, limit=25))
        assert len(collected) == 25
        # No duplicates by id
        assert len({law.id for law in collected}) == len(collected)

    def test_iter_across_multiple_pages(self, client: Legalize):
        # Collect 150 laws → forces at least 2 pages at per_page=100.
        collected = list(client.laws.iter("es", per_page=100, limit=150))
        assert len(collected) == 150
        assert len({law.id for law in collected}) == 150


# ---- auth / errors ---------------------------------------------------


class TestAuthErrors:
    def test_bad_key_401(self, base_url: str):
        from legalize import AuthenticationError

        c = Legalize(api_key="leg_invalid_key_xxx", base_url=base_url)
        try:
            with pytest.raises(AuthenticationError):
                c.countries.list()
        finally:
            c.close()

    def test_nonexistent_country_404(self, client: Legalize):
        with pytest.raises(NotFoundError):
            client.stats.retrieve("zz")
