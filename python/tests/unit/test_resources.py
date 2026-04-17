"""Resource endpoints — verifies request shape (method, URL, params, body)
and response parsing into typed models.
"""

from __future__ import annotations

import httpx
import pytest

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


def _json(request: httpx.Request, status: int, body):
    return httpx.Response(status, json=body, request=request)


def capture(handler_slot, status=200, body=None):
    """Install a handler that records the incoming request and returns body."""

    received: dict[str, httpx.Request] = {}

    def h(req: httpx.Request) -> httpx.Response:
        received["request"] = req
        return httpx.Response(status, json=body if body is not None else {}, request=req)

    handler_slot[0] = h
    return received


# ---- countries ---------------------------------------------------------


class TestCountries:
    def test_list(self, client, handler):
        received = capture(
            handler, body=[{"country": "es", "count": 100}, {"country": "fr", "count": 50}]
        )
        out = client.countries.list()
        assert received["request"].method == "GET"
        assert received["request"].url.path == "/api/v1/countries"
        assert all(isinstance(c, CountryInfo) for c in out)
        assert [c.country for c in out] == ["es", "fr"]

    def test_auth_header(self, client, handler):
        capture(handler, body=[])
        client.countries.list()
        # Authorization is always set
        assert handler[0] is not None

    @pytest.mark.asyncio
    async def test_async_list(self, aclient, handler):
        received = capture(handler, body=[{"country": "es", "count": 10}])
        out = await aclient.countries.list()
        assert received["request"].url.path == "/api/v1/countries"
        assert out[0].country == "es"
        await aclient.aclose()


# ---- jurisdictions -----------------------------------------------------


class TestJurisdictions:
    def test_list(self, client, handler):
        received = capture(handler, body=[{"jurisdiction": "catalonia", "count": 50}])
        out = client.jurisdictions.list("es")
        assert received["request"].url.path == "/api/v1/es/jurisdictions"
        assert isinstance(out[0], JurisdictionInfo)


# ---- law_types ---------------------------------------------------------


class TestLawTypes:
    def test_list(self, client, handler):
        received = capture(handler, body=["constitucion", "ley", "real_decreto"])
        out = client.law_types.list("es")
        assert received["request"].url.path == "/api/v1/es/law-types"
        assert out == ["constitucion", "ley", "real_decreto"]


# ---- laws --------------------------------------------------------------


LAW_META = {
    "id": "ley_organica_3_2018",
    "country": "es",
    "law_type": "ley_organica",
    "title": "Ley Orgánica 3/2018",
}


class TestLaws:
    def test_list_with_filters(self, client, handler):
        received = capture(
            handler,
            body={
                "country": "es",
                "total": 2,
                "page": 1,
                "per_page": 50,
                "results": [dict(LAW_META), dict(LAW_META, id="y")],
            },
        )
        out = client.laws.list(
            "es",
            page=1,
            per_page=50,
            law_type=["ley_organica", "ley"],
            year=2018,
            status="vigente",
        )
        assert isinstance(out, PaginatedLaws)
        q = dict(received["request"].url.params)
        assert q["law_type"] == "ley_organica,ley"
        assert q["year"] == "2018"
        assert q["status"] == "vigente"
        assert q["page"] == "1"
        assert q["per_page"] == "50"

    def test_search_requires_q(self, client):
        with pytest.raises(ValueError, match="q must be"):
            client.laws.search("es", q="")
        with pytest.raises(ValueError, match="q must be"):
            client.laws.search("es", q="   ")

    def test_search_sets_q(self, client, handler):
        received = capture(
            handler,
            body={
                "country": "es",
                "total": 1,
                "page": 1,
                "per_page": 50,
                "query": "privacidad",
                "results": [dict(LAW_META)],
            },
        )
        out = client.laws.search("es", q="privacidad")
        assert dict(received["request"].url.params)["q"] == "privacidad"
        assert out.total == 1

    def test_iter_paginates(self, client, handler):
        # Return 2 pages of 2 items each, total=4.
        pages = [
            {
                "country": "es",
                "total": 4,
                "page": 1,
                "per_page": 2,
                "results": [{**LAW_META, "id": "a"}, {**LAW_META, "id": "b"}],
            },
            {
                "country": "es",
                "total": 4,
                "page": 2,
                "per_page": 2,
                "results": [{**LAW_META, "id": "c"}, {**LAW_META, "id": "d"}],
            },
        ]
        call_idx = [0]

        def h(req: httpx.Request) -> httpx.Response:
            resp = httpx.Response(200, json=pages[call_idx[0]], request=req)
            call_idx[0] += 1
            return resp

        handler[0] = h
        ids = [law.id for law in client.laws.iter("es", per_page=2)]
        assert ids == ["a", "b", "c", "d"]

    def test_retrieve(self, client, handler):
        received = capture(handler, body={**LAW_META, "content_md": "# Body"})
        out = client.laws.retrieve("es", "ley_organica_3_2018")
        assert received["request"].url.path == "/api/v1/es/laws/ley_organica_3_2018"
        assert isinstance(out, LawDetail)
        assert out.content_md == "# Body"

    def test_meta(self, client, handler):
        received = capture(handler, body=LAW_META)
        out = client.laws.meta("es", "ley_organica_3_2018")
        assert received["request"].url.path.endswith("/meta")
        assert isinstance(out, LawMeta)

    def test_commits(self, client, handler):
        received = capture(
            handler,
            body={
                "law_id": "x",
                "commits": [
                    {"sha": "abc1234", "date": "2024-01-01", "message": "Initial"},
                ],
            },
        )
        out = client.laws.commits("es", "x")
        assert received["request"].url.path.endswith("/commits")
        assert isinstance(out, CommitsResponse)
        assert out.commits[0].sha == "abc1234"

    def test_at_commit(self, client, handler):
        received = capture(
            handler,
            body={"law_id": "x", "sha": "abc1234", "content_md": "# Historical"},
        )
        out = client.laws.at_commit("es", "x", "abc1234")
        assert received["request"].url.path == "/api/v1/es/laws/x/at/abc1234"
        assert isinstance(out, LawAtCommitResponse)


# ---- reforms -----------------------------------------------------------


class TestReforms:
    def test_list(self, client, handler):
        received = capture(
            handler,
            body={
                "law_id": "x",
                "total": 1,
                "offset": 0,
                "limit": 100,
                "reforms": [{"date": "2024-01-01", "source_id": "s1"}],
            },
        )
        out = client.reforms.list("es", "x")
        q = dict(received["request"].url.params)
        assert q["limit"] == "100"
        assert q["offset"] == "0"
        assert isinstance(out, ReformsResponse)

    def test_iter(self, client, handler):
        pages = [
            {
                "law_id": "x",
                "total": 3,
                "offset": 0,
                "limit": 2,
                "reforms": [
                    {"date": "2024-01-01", "source_id": "a"},
                    {"date": "2024-01-02", "source_id": "b"},
                ],
            },
            {
                "law_id": "x",
                "total": 3,
                "offset": 2,
                "limit": 2,
                "reforms": [{"date": "2024-01-03", "source_id": "c"}],
            },
        ]
        idx = [0]

        def h(req):
            resp = httpx.Response(200, json=pages[idx[0]], request=req)
            idx[0] += 1
            return resp

        handler[0] = h
        ids = [r.source_id for r in client.reforms.iter("es", "x", batch=2)]
        assert ids == ["a", "b", "c"]


# ---- stats -------------------------------------------------------------


class TestStats:
    def test_retrieve(self, client, handler):
        received = capture(
            handler,
            body={
                "country": "es",
                "jurisdiction": None,
                "reform_activity_by_year": [{"year": 2024, "count": 100}],
                "most_reformed_laws": [{"id": "x", "title": "T", "count": 50}],
                "law_types": ["ley"],
            },
        )
        out = client.stats.retrieve("es")
        assert received["request"].url.path == "/api/v1/es/stats"
        assert isinstance(out, StatsResponse)

    def test_jurisdiction_filter(self, client, handler):
        received = capture(
            handler,
            body={
                "country": "es",
                "jurisdiction": "catalonia",
                "reform_activity_by_year": [],
                "most_reformed_laws": [],
                "law_types": [],
            },
        )
        client.stats.retrieve("es", jurisdiction="catalonia")
        assert dict(received["request"].url.params)["jurisdiction"] == "catalonia"


# ---- webhooks ----------------------------------------------------------


class TestWebhooksResource:
    def test_create(self, client, handler):
        received = capture(
            handler,
            body={
                "id": 1,
                "url": "https://example.test/hook",
                "secret": "whsec_abcdefghij",
                "event_types": ["law.updated"],
                "countries": ["es"],
                "description": "",
                "enabled": True,
                "created_at": "2026-04-01T00:00:00Z",
            },
        )
        out = client.webhooks.create(
            url="https://example.test/hook",
            event_types=["law.updated"],
            countries=["es"],
        )
        req = received["request"]
        assert req.method == "POST"
        assert req.url.path == "/api/v1/webhooks"
        import json as jsonlib

        body = jsonlib.loads(req.content)
        assert body["url"] == "https://example.test/hook"
        assert body["event_types"] == ["law.updated"]
        assert out["secret"].startswith("whsec_")

    def test_list(self, client, handler):
        capture(handler, body=[{"id": 1, "url": "u", "enabled": True}])
        assert client.webhooks.list() == [{"id": 1, "url": "u", "enabled": True}]

    def test_retrieve(self, client, handler):
        received = capture(handler, body={"id": 7, "url": "u"})
        client.webhooks.retrieve(7)
        assert received["request"].url.path == "/api/v1/webhooks/7"

    def test_update(self, client, handler):
        received = capture(handler, body={"id": 7, "enabled": False})
        client.webhooks.update(7, enabled=False, description="paused")
        req = received["request"]
        assert req.method == "PATCH"
        import json as jsonlib

        body = jsonlib.loads(req.content)
        assert body == {"description": "paused", "enabled": False}

    def test_delete(self, client, handler):
        received = capture(handler, body={"status": "deleted"})
        out = client.webhooks.delete(7)
        assert received["request"].method == "DELETE"
        assert out == {"status": "deleted"}

    def test_deliveries_params(self, client, handler):
        received = capture(handler, body={"total": 0, "deliveries": []})
        client.webhooks.deliveries(7, page=2, status="failed")
        q = dict(received["request"].url.params)
        assert q["page"] == "2"
        assert q["status"] == "failed"

    def test_deliveries_rejects_bad_status(self, client):
        with pytest.raises(ValueError, match="status"):
            client.webhooks.deliveries(7, status="weird")

    def test_retry(self, client, handler):
        received = capture(handler, body={"status": "success"})
        client.webhooks.retry(7, 42)
        assert received["request"].url.path == "/api/v1/webhooks/7/deliveries/42/retry"

    def test_test_ping(self, client, handler):
        received = capture(handler, body={"status": "success"})
        client.webhooks.test(7)
        assert received["request"].url.path == "/api/v1/webhooks/7/test"
