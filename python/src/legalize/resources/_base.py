"""Resource base classes.

Resources are bound to a client instance at construction. They never
build requests themselves beyond assembling params and the path —
transport, auth and retries live on the client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from legalize._client import AsyncLegalize, Legalize


API = "/api/v1"


class _SyncResource:
    """Holds a reference to the sync client."""

    def __init__(self, client: Legalize) -> None:
        self._client = client


class _AsyncResource:
    """Holds a reference to the async client."""

    def __init__(self, client: AsyncLegalize) -> None:
        self._client = client


__all__ = ["API", "_AsyncResource", "_SyncResource"]
