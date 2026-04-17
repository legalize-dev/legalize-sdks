"""``/api/v1/{country}/laws/{law_id}/reforms`` — reform history."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

from legalize._pagination import AsyncOffsetIterator, OffsetIterator
from legalize.models import Reform, ReformsResponse
from legalize.resources._base import API, _AsyncResource, _SyncResource


class Reforms(_SyncResource):
    def list(
        self,
        country: str,
        law_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> ReformsResponse:
        """Return a single page of reforms for a law."""
        data = self._client.request(
            "GET",
            f"{API}/{country}/laws/{law_id}/reforms",
            params={"limit": limit, "offset": offset},
        )
        return ReformsResponse.model_validate(data)

    def iter(
        self,
        country: str,
        law_id: str,
        *,
        batch: int = 100,
        limit: int | None = None,
    ) -> Iterator[Reform]:
        """Auto-paginate across every reform for a law."""

        def fetch(batch_size: int, offset: int) -> tuple[list[Reform], int]:
            resp = self.list(country, law_id, limit=batch_size, offset=offset)
            return resp.reforms, resp.total

        return iter(OffsetIterator(fetch, batch=batch, limit=limit))


class AsyncReforms(_AsyncResource):
    async def list(
        self,
        country: str,
        law_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> ReformsResponse:
        data = await self._client.request(
            "GET",
            f"{API}/{country}/laws/{law_id}/reforms",
            params={"limit": limit, "offset": offset},
        )
        return ReformsResponse.model_validate(data)

    def iter(
        self,
        country: str,
        law_id: str,
        *,
        batch: int = 100,
        limit: int | None = None,
    ) -> AsyncIterator[Reform]:
        async def fetch(batch_size: int, offset: int) -> tuple[list[Reform], int]:
            resp = await self.list(country, law_id, limit=batch_size, offset=offset)
            return resp.reforms, resp.total

        return AsyncOffsetIterator(fetch, batch=batch, limit=limit).__aiter__()


__all__ = ["AsyncReforms", "Reforms"]
