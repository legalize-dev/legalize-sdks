"""``/api/v1/{country}/jurisdictions`` — regions/states within a country."""

from __future__ import annotations

from legalize.models import JurisdictionInfo
from legalize.resources._base import API, _AsyncResource, _SyncResource


class Jurisdictions(_SyncResource):
    def list(self, country: str) -> list[JurisdictionInfo]:
        """List jurisdictions for a country (e.g. Spain's comunidades)."""
        data = self._client.request("GET", f"{API}/{country}/jurisdictions")
        return [JurisdictionInfo.model_validate(item) for item in data]


class AsyncJurisdictions(_AsyncResource):
    async def list(self, country: str) -> list[JurisdictionInfo]:
        data = await self._client.request("GET", f"{API}/{country}/jurisdictions")
        return [JurisdictionInfo.model_validate(item) for item in data]


__all__ = ["AsyncJurisdictions", "Jurisdictions"]
