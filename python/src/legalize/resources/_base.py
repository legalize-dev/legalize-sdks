"""Resource base classes.

Resources are bound to a client instance at construction. They never
build requests themselves beyond assembling params and the path —
transport, auth and retries live on the client.

Resources depend on a minimal :class:`ClientProtocol` rather than the
concrete :class:`legalize.Legalize` class. This keeps the module-level
dependency graph a DAG (resources → protocol; client → resources) with
no cyclic import, while still giving resources the exact method they
need in a fully typed way.
"""

from __future__ import annotations

from typing import Any, Protocol

API = "/api/v1"


class ClientProtocol(Protocol):
    """The surface a synchronous resource needs from its client."""

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = ...,
        json: Any = ...,
        extra_headers: dict[str, str] | None = ...,
    ) -> Any: ...


class AsyncClientProtocol(Protocol):
    """The surface an asynchronous resource needs from its client."""

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = ...,
        json: Any = ...,
        extra_headers: dict[str, str] | None = ...,
    ) -> Any: ...


class _SyncResource:
    """Holds a reference to a sync-capable client."""

    def __init__(self, client: ClientProtocol) -> None:
        self._client = client


class _AsyncResource:
    """Holds a reference to an async-capable client."""

    def __init__(self, client: AsyncClientProtocol) -> None:
        self._client = client


__all__ = [
    "API",
    "AsyncClientProtocol",
    "ClientProtocol",
    "_AsyncResource",
    "_SyncResource",
]
