"""``/api/v1/{country}/laws`` and sub-resources.

Covers:

- ``list``/``search``          — listing vs. full-text search
- ``iter``/``search_iter``     — auto-paginated iterators
- ``retrieve``                 — full law with Markdown content
- ``meta``                     — metadata only (fast)
- ``commits``                  — git commit history
- ``at_commit``                — time-travel to a specific SHA
- ``at_date``                  — time-travel to a date, SHA resolved for you

Every listing and search method takes ``text_state`` to filter on what the body
of a law actually is: ``point_in_time`` (the law as in force on its date),
``current`` (the latest text the source publishes) or ``as_enacted`` (the act as
published, amendments not folded in). Omit it and you get every state, which is
what the endpoint has always returned.

Each result carries ``text_state`` with the same vocabulary, ``reform_count``,
and ``text_superseded`` — the answer to "can I quote this as the law in force?".
A law can be in force and its text still be superseded: 166,422 of Portugal's
171,739 acts are served as enacted.

Do not derive ``text_superseded`` from ``reform_count`` yourself. Where a source
publishes the same act twice, the amendments are recorded against the
consolidated copy and the as-published one reports zero while being out of date
— 227 of Portugal's laws. The server resolves that; the field is the answer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from legalize._pagination import AsyncPageIterator, PageIterator
from legalize.models import (
    CommitsResponse,
    LawAtCommitResponse,
    LawAtDateResponse,
    LawDetail,
    LawMeta,
    LawSearchResult,
    PaginatedLaws,
)
from legalize.resources._base import API, _AsyncResource, _SyncResource

# Alias so type hints inside classes that define a ``list`` method still
# resolve to the builtin. Mypy picks the method over the type otherwise.
_L = list


def _filter_params(
    *,
    law_type: str | _L[str] | None,
    year: int | None,
    status: str | None,
    jurisdiction: str | None,
    from_date: str | None,
    to_date: str | None,
    sort: str | None,
    text_state: str | None = None,
    page: int | None = None,
    per_page: int | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "law_type": law_type,
        "year": year,
        "status": status,
        "jurisdiction": jurisdiction,
        "from_date": from_date,
        "to_date": to_date,
        "sort": sort,
        "text_state": text_state,
        "page": page,
        "per_page": per_page,
        "q": q,
    }
    return params


class Laws(_SyncResource):
    # ---- list / search --------------------------------------------------

    def list(
        self,
        country: str,
        *,
        page: int = 1,
        per_page: int = 50,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> PaginatedLaws:
        """Return a single page of laws for a country."""
        params = _filter_params(
            law_type=law_type,
            year=year,
            status=status,
            jurisdiction=jurisdiction,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            text_state=text_state,
            page=page,
            per_page=per_page,
        )
        data = self._client.request("GET", f"{API}/{country}/laws", params=params)
        return PaginatedLaws.model_validate(data)

    def search(
        self,
        country: str,
        *,
        q: str,
        page: int = 1,
        per_page: int = 50,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> PaginatedLaws:
        """Full-text search for laws. ``q`` is required."""
        if not q or not q.strip():
            raise ValueError("q must be a non-empty search query")
        params = _filter_params(
            law_type=law_type,
            year=year,
            status=status,
            jurisdiction=jurisdiction,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            text_state=text_state,
            page=page,
            per_page=per_page,
            q=q,
        )
        data = self._client.request("GET", f"{API}/{country}/laws", params=params)
        return PaginatedLaws.model_validate(data)

    def iter(
        self,
        country: str,
        *,
        per_page: int = 100,
        limit: int | None = None,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> Iterator[LawSearchResult]:
        """Auto-paginate across every matching law."""

        def fetch(page: int, per: int) -> tuple[list[LawSearchResult], int]:
            resp = self.list(
                country,
                page=page,
                per_page=per,
                law_type=law_type,
                year=year,
                status=status,
                jurisdiction=jurisdiction,
                from_date=from_date,
                to_date=to_date,
                sort=sort,
                text_state=text_state,
            )
            return resp.results, resp.total

        return iter(PageIterator(fetch, per_page=per_page, limit=limit))

    def search_iter(
        self,
        country: str,
        *,
        q: str,
        per_page: int = 100,
        limit: int | None = None,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> Iterator[LawSearchResult]:
        """Auto-paginate across every match of a full-text search."""
        if not q or not q.strip():
            raise ValueError("q must be a non-empty search query")

        def fetch(page: int, per: int) -> tuple[list[LawSearchResult], int]:
            resp = self.search(
                country,
                q=q,
                page=page,
                per_page=per,
                law_type=law_type,
                year=year,
                status=status,
                jurisdiction=jurisdiction,
                from_date=from_date,
                to_date=to_date,
                sort=sort,
                text_state=text_state,
            )
            return resp.results, resp.total

        return iter(PageIterator(fetch, per_page=per_page, limit=limit))

    # ---- retrieve -------------------------------------------------------

    def retrieve(self, country: str, law_id: str) -> LawDetail:
        """Fetch the full law including Markdown content."""
        data = self._client.request("GET", f"{API}/{country}/laws/{law_id}")
        return LawDetail.model_validate(data)

    def meta(self, country: str, law_id: str) -> LawMeta:
        """Fetch only the law metadata (no content)."""
        data = self._client.request("GET", f"{API}/{country}/laws/{law_id}/meta")
        return LawMeta.model_validate(data)

    def commits(self, country: str, law_id: str) -> CommitsResponse:
        """Git commit history for the law."""
        data = self._client.request("GET", f"{API}/{country}/laws/{law_id}/commits")
        return CommitsResponse.model_validate(data)

    def at_commit(self, country: str, law_id: str, sha: str) -> LawAtCommitResponse:
        """Return the law's full text at a specific historical version."""
        data = self._client.request("GET", f"{API}/{country}/laws/{law_id}/at/{sha}")
        return LawAtCommitResponse.model_validate(data)

    def at_date(self, country: str, law_id: str, date: str) -> LawAtDateResponse:
        """Return the law's full text as published on or before ``date``.

        The server resolves the date to a version, so callers do not have to
        walk :meth:`commits` looking for a SHA. The response carries the
        resolved ``sha`` and ``version_date`` so the answer stays verifiable.

        The rule is *published on or before* ``date``, not *in force on* it:
        the dates are official publication dates, so a reform still inside its
        vacatio legis resolves as already applying. Cite accordingly.

        Args:
            country: Country code, e.g. ``"es"``.
            law_id: Official identifier, e.g. ``"BOE-A-2003-23186"``.
            date: Point in time as ``YYYY-MM-DD``.
        """
        data = self._client.request(
            "GET", f"{API}/{country}/laws/{law_id}/at", params={"date": date}
        )
        return LawAtDateResponse.model_validate(data)


class AsyncLaws(_AsyncResource):
    async def list(
        self,
        country: str,
        *,
        page: int = 1,
        per_page: int = 50,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> PaginatedLaws:
        params = _filter_params(
            law_type=law_type,
            year=year,
            status=status,
            jurisdiction=jurisdiction,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            text_state=text_state,
            page=page,
            per_page=per_page,
        )
        data = await self._client.request("GET", f"{API}/{country}/laws", params=params)
        return PaginatedLaws.model_validate(data)

    async def search(
        self,
        country: str,
        *,
        q: str,
        page: int = 1,
        per_page: int = 50,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> PaginatedLaws:
        if not q or not q.strip():
            raise ValueError("q must be a non-empty search query")
        params = _filter_params(
            law_type=law_type,
            year=year,
            status=status,
            jurisdiction=jurisdiction,
            from_date=from_date,
            to_date=to_date,
            sort=sort,
            text_state=text_state,
            page=page,
            per_page=per_page,
            q=q,
        )
        data = await self._client.request("GET", f"{API}/{country}/laws", params=params)
        return PaginatedLaws.model_validate(data)

    def iter(
        self,
        country: str,
        *,
        per_page: int = 100,
        limit: int | None = None,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> AsyncIterator[LawSearchResult]:
        async def fetch(page: int, per: int) -> tuple[list[LawSearchResult], int]:
            resp = await self.list(
                country,
                page=page,
                per_page=per,
                law_type=law_type,
                year=year,
                status=status,
                jurisdiction=jurisdiction,
                from_date=from_date,
                to_date=to_date,
                sort=sort,
                text_state=text_state,
            )
            return resp.results, resp.total

        return AsyncPageIterator(fetch, per_page=per_page, limit=limit).__aiter__()

    def search_iter(
        self,
        country: str,
        *,
        q: str,
        per_page: int = 100,
        limit: int | None = None,
        law_type: str | _L[str] | None = None,
        year: int | None = None,
        status: str | None = None,
        jurisdiction: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        sort: str | None = None,
        text_state: str | None = None,
    ) -> AsyncIterator[LawSearchResult]:
        """Auto-paginate across every match of a full-text search."""
        if not q or not q.strip():
            raise ValueError("q must be a non-empty search query")

        async def fetch(page: int, per: int) -> tuple[list[LawSearchResult], int]:
            resp = await self.search(
                country,
                q=q,
                page=page,
                per_page=per,
                law_type=law_type,
                year=year,
                status=status,
                jurisdiction=jurisdiction,
                from_date=from_date,
                to_date=to_date,
                sort=sort,
                text_state=text_state,
            )
            return resp.results, resp.total

        return AsyncPageIterator(fetch, per_page=per_page, limit=limit).__aiter__()

    async def retrieve(self, country: str, law_id: str) -> LawDetail:
        data = await self._client.request("GET", f"{API}/{country}/laws/{law_id}")
        return LawDetail.model_validate(data)

    async def meta(self, country: str, law_id: str) -> LawMeta:
        data = await self._client.request("GET", f"{API}/{country}/laws/{law_id}/meta")
        return LawMeta.model_validate(data)

    async def commits(self, country: str, law_id: str) -> CommitsResponse:
        data = await self._client.request("GET", f"{API}/{country}/laws/{law_id}/commits")
        return CommitsResponse.model_validate(data)

    async def at_commit(self, country: str, law_id: str, sha: str) -> LawAtCommitResponse:
        data = await self._client.request("GET", f"{API}/{country}/laws/{law_id}/at/{sha}")
        return LawAtCommitResponse.model_validate(data)

    async def at_date(self, country: str, law_id: str, date: str) -> LawAtDateResponse:
        """Return the law's full text as published on or before ``date``.

        Async twin of :meth:`Laws.at_date`.
        """
        data = await self._client.request(
            "GET", f"{API}/{country}/laws/{law_id}/at", params={"date": date}
        )
        return LawAtDateResponse.model_validate(data)


__all__ = ["AsyncLaws", "Laws"]
