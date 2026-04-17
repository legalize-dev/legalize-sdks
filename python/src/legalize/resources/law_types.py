"""``/api/v1/{country}/law-types`` — law types per country (constitucion, ley, ...)."""

from __future__ import annotations

from legalize.resources._base import API, _AsyncResource, _SyncResource


class LawTypes(_SyncResource):
    def list(self, country: str) -> list[str]:
        data = self._client.request("GET", f"{API}/{country}/law-types")
        return list(data)


class AsyncLawTypes(_AsyncResource):
    async def list(self, country: str) -> list[str]:
        data = await self._client.request("GET", f"{API}/{country}/law-types")
        return list(data)


__all__ = ["AsyncLawTypes", "LawTypes"]
