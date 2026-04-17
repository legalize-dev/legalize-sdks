"""``/api/v1/{country}/stats`` — aggregate statistics for a country."""

from __future__ import annotations

from typing import Any

from legalize.models import StatsResponse
from legalize.resources._base import API, _AsyncResource, _SyncResource


class Stats(_SyncResource):
    def retrieve(self, country: str, *, jurisdiction: str | None = None) -> StatsResponse:
        params: dict[str, Any] = {"jurisdiction": jurisdiction}
        data = self._client.request("GET", f"{API}/{country}/stats", params=params)
        return StatsResponse.model_validate(data)


class AsyncStats(_AsyncResource):
    async def retrieve(self, country: str, *, jurisdiction: str | None = None) -> StatsResponse:
        params: dict[str, Any] = {"jurisdiction": jurisdiction}
        data = await self._client.request("GET", f"{API}/{country}/stats", params=params)
        return StatsResponse.model_validate(data)


__all__ = ["AsyncStats", "Stats"]
