"""``/api/v1/webhooks`` CRUD + delivery history + test ping.

The management endpoints (this module) require Pro+ tier. The webhook
signature verification utility lives in :mod:`legalize.webhooks` and
has no API dependency — it runs on the recipient's server.
"""

from __future__ import annotations

from typing import Any, cast

from legalize.resources._base import API, _AsyncResource, _SyncResource

# Local alias: inside these classes a method named ``list`` shadows the
# builtin when used as a type annotation. Binding an alias at module
# scope gives us a name we can use in signatures without collision.
_L = list
_Dict = dict[str, Any]
_DictList = list[_Dict]


class Webhooks(_SyncResource):
    # ---- endpoints (CRUD) ----------------------------------------------

    def create(
        self,
        *,
        url: str,
        event_types: _L[str],
        countries: _L[str] | None = None,
        description: str = "",
    ) -> _Dict:
        """Create a webhook endpoint. Returns the signing secret ONCE."""
        body = {
            "url": url,
            "event_types": event_types,
            "countries": countries,
            "description": description,
        }
        return cast(_Dict, self._client.request("POST", f"{API}/webhooks", json=body))

    def list(self) -> _DictList:
        """List all webhook endpoints for the authenticated org."""
        return list(self._client.request("GET", f"{API}/webhooks"))

    def retrieve(self, endpoint_id: int) -> _Dict:
        """Fetch a single endpoint by id."""
        return cast(_Dict, self._client.request("GET", f"{API}/webhooks/{endpoint_id}"))

    def update(
        self,
        endpoint_id: int,
        *,
        url: str | None = None,
        event_types: _L[str] | None = None,
        countries: _L[str] | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> _Dict:
        body = {
            k: v
            for k, v in {
                "url": url,
                "event_types": event_types,
                "countries": countries,
                "description": description,
                "enabled": enabled,
            }.items()
            if v is not None
        }
        return cast(
            _Dict, self._client.request("PATCH", f"{API}/webhooks/{endpoint_id}", json=body)
        )

    def delete(self, endpoint_id: int) -> _Dict:
        return cast(_Dict, self._client.request("DELETE", f"{API}/webhooks/{endpoint_id}"))

    # ---- deliveries + tests --------------------------------------------

    def deliveries(
        self,
        endpoint_id: int,
        *,
        page: int = 1,
        status: str | None = None,
    ) -> _Dict:
        """List delivery attempts for an endpoint.

        ``status`` filters to ``failed``/``success``/``pending``.
        """
        if status is not None and status not in ("failed", "success", "pending"):
            raise ValueError("status must be 'failed', 'success', 'pending', or None")
        params: _Dict = {"page": page, "status": status}
        return cast(
            _Dict,
            self._client.request(
                "GET", f"{API}/webhooks/{endpoint_id}/deliveries", params=params
            ),
        )

    def retry(self, endpoint_id: int, delivery_id: int) -> _Dict:
        """Retry a failed delivery."""
        return cast(
            _Dict,
            self._client.request(
                "POST",
                f"{API}/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry",
            ),
        )

    def test(self, endpoint_id: int) -> _Dict:
        """Send a ``test.ping`` event to verify the endpoint is reachable."""
        return cast(_Dict, self._client.request("POST", f"{API}/webhooks/{endpoint_id}/test"))


class AsyncWebhooks(_AsyncResource):
    async def create(
        self,
        *,
        url: str,
        event_types: _L[str],
        countries: _L[str] | None = None,
        description: str = "",
    ) -> _Dict:
        body = {
            "url": url,
            "event_types": event_types,
            "countries": countries,
            "description": description,
        }
        return cast(
            _Dict, await self._client.request("POST", f"{API}/webhooks", json=body)
        )

    async def list(self) -> _DictList:
        data = await self._client.request("GET", f"{API}/webhooks")
        return list(data)

    async def retrieve(self, endpoint_id: int) -> _Dict:
        return cast(
            _Dict, await self._client.request("GET", f"{API}/webhooks/{endpoint_id}")
        )

    async def update(
        self,
        endpoint_id: int,
        *,
        url: str | None = None,
        event_types: _L[str] | None = None,
        countries: _L[str] | None = None,
        description: str | None = None,
        enabled: bool | None = None,
    ) -> _Dict:
        body = {
            k: v
            for k, v in {
                "url": url,
                "event_types": event_types,
                "countries": countries,
                "description": description,
                "enabled": enabled,
            }.items()
            if v is not None
        }
        return cast(
            _Dict,
            await self._client.request("PATCH", f"{API}/webhooks/{endpoint_id}", json=body),
        )

    async def delete(self, endpoint_id: int) -> _Dict:
        return cast(
            _Dict, await self._client.request("DELETE", f"{API}/webhooks/{endpoint_id}")
        )

    async def deliveries(
        self,
        endpoint_id: int,
        *,
        page: int = 1,
        status: str | None = None,
    ) -> _Dict:
        if status is not None and status not in ("failed", "success", "pending"):
            raise ValueError("status must be 'failed', 'success', 'pending', or None")
        params: _Dict = {"page": page, "status": status}
        return cast(
            _Dict,
            await self._client.request(
                "GET", f"{API}/webhooks/{endpoint_id}/deliveries", params=params
            ),
        )

    async def retry(self, endpoint_id: int, delivery_id: int) -> _Dict:
        return cast(
            _Dict,
            await self._client.request(
                "POST",
                f"{API}/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry",
            ),
        )

    async def test(self, endpoint_id: int) -> _Dict:
        return cast(
            _Dict, await self._client.request("POST", f"{API}/webhooks/{endpoint_id}/test")
        )


__all__ = ["AsyncWebhooks", "Webhooks"]
