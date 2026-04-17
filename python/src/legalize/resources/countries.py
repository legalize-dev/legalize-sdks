"""``/api/v1/countries`` — list all available countries."""

from __future__ import annotations

from legalize.models import CountryInfo
from legalize.resources._base import API, _AsyncResource, _SyncResource


class Countries(_SyncResource):
    def list(self) -> list[CountryInfo]:
        """Return every country the API serves, with law counts."""
        data = self._client.request("GET", f"{API}/countries")
        return [CountryInfo.model_validate(item) for item in data]


class AsyncCountries(_AsyncResource):
    async def list(self) -> list[CountryInfo]:
        data = await self._client.request("GET", f"{API}/countries")
        return [CountryInfo.model_validate(item) for item in data]


__all__ = ["AsyncCountries", "Countries"]
