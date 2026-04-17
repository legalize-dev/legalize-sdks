"""Pagination helpers.

The Legalize API uses offset-based pagination for laws and reforms:

- ``/api/v1/{country}/laws`` — ``page`` (1-indexed) + ``per_page`` (max 100)
- ``/api/v1/{country}/laws/{id}/reforms`` — ``limit`` + ``offset``
- ``/api/v1/webhooks/{id}/deliveries`` — ``page``

Each page response carries ``total`` (true match count from COUNT(*)).
That lets us iterate to completion without inferring end-of-stream.

The two iterators here are thin wrappers. They own the request
construction but delegate the actual HTTP call to a ``fetcher``
callback, so they work for both sync and async clients.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")

PAGE_MAX = 100  # API enforces per_page ≤ 100


class PageIterator(Generic[T]):
    """Synchronous auto-paginator over a page-based endpoint.

    ``fetch_page`` receives ``(page, per_page)`` and returns a tuple
    ``(items, total)``. The iterator yields items one at a time and
    transparently advances pages until ``total`` items have been
    returned or a short page is observed (defensive).

    Passing ``limit`` caps the total number of items yielded regardless
    of server total.
    """

    def __init__(
        self,
        fetch_page: Callable[[int, int], tuple[list[T], int]],
        *,
        per_page: int = PAGE_MAX,
        limit: int | None = None,
        start_page: int = 1,
    ) -> None:
        if per_page < 1 or per_page > PAGE_MAX:
            raise ValueError(f"per_page must be between 1 and {PAGE_MAX}")
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        self._fetch_page = fetch_page
        self._per_page = per_page
        self._limit = limit
        self._page = start_page

    def __iter__(self) -> Iterator[T]:
        yielded = 0
        page = self._page
        while True:
            if self._limit is not None and yielded >= self._limit:
                return
            items, total = self._fetch_page(page, self._per_page)
            if not items:
                return
            for item in items:
                if self._limit is not None and yielded >= self._limit:
                    return
                yield item
                yielded += 1
            # Stop when the server told us total and we've drained it,
            # OR when a short page arrives (defensive against servers
            # that don't return a reliable total).
            if yielded >= total:
                return
            if len(items) < self._per_page:
                return
            page += 1


class AsyncPageIterator(Generic[T]):
    """Async counterpart of :class:`PageIterator`."""

    def __init__(
        self,
        fetch_page: Callable[[int, int], Awaitable[tuple[list[T], int]]],
        *,
        per_page: int = PAGE_MAX,
        limit: int | None = None,
        start_page: int = 1,
    ) -> None:
        if per_page < 1 or per_page > PAGE_MAX:
            raise ValueError(f"per_page must be between 1 and {PAGE_MAX}")
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        self._fetch_page = fetch_page
        self._per_page = per_page
        self._limit = limit
        self._page = start_page

    async def __aiter__(self) -> AsyncIterator[T]:
        yielded = 0
        page = self._page
        while True:
            if self._limit is not None and yielded >= self._limit:
                return
            items, total = await self._fetch_page(page, self._per_page)
            if not items:
                return
            for item in items:
                if self._limit is not None and yielded >= self._limit:
                    return
                yield item
                yielded += 1
            if yielded >= total:
                return
            if len(items) < self._per_page:
                return
            page += 1


class OffsetIterator(Generic[T]):
    """Sync auto-paginator for offset/limit endpoints (reforms).

    ``fetch_page(limit, offset)`` returns ``(items, total)``.
    """

    def __init__(
        self,
        fetch_page: Callable[[int, int], tuple[list[T], int]],
        *,
        batch: int = 100,
        limit: int | None = None,
        start_offset: int = 0,
    ) -> None:
        if batch < 1:
            raise ValueError("batch must be >= 1")
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        self._fetch_page = fetch_page
        self._batch = batch
        self._limit = limit
        self._offset = start_offset

    def __iter__(self) -> Iterator[T]:
        yielded = 0
        offset = self._offset
        while True:
            if self._limit is not None and yielded >= self._limit:
                return
            items, total = self._fetch_page(self._batch, offset)
            if not items:
                return
            for item in items:
                if self._limit is not None and yielded >= self._limit:
                    return
                yield item
                yielded += 1
            offset += len(items)
            if offset >= total:
                return
            if len(items) < self._batch:
                return


class AsyncOffsetIterator(Generic[T]):
    """Async counterpart of :class:`OffsetIterator`."""

    def __init__(
        self,
        fetch_page: Callable[[int, int], Awaitable[tuple[list[T], int]]],
        *,
        batch: int = 100,
        limit: int | None = None,
        start_offset: int = 0,
    ) -> None:
        if batch < 1:
            raise ValueError("batch must be >= 1")
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        self._fetch_page = fetch_page
        self._batch = batch
        self._limit = limit
        self._offset = start_offset

    async def __aiter__(self) -> AsyncIterator[T]:
        yielded = 0
        offset = self._offset
        while True:
            if self._limit is not None and yielded >= self._limit:
                return
            items, total = await self._fetch_page(self._batch, offset)
            if not items:
                return
            for item in items:
                if self._limit is not None and yielded >= self._limit:
                    return
                yield item
                yielded += 1
            offset += len(items)
            if offset >= total:
                return
            if len(items) < self._batch:
                return


__all__ = [
    "PAGE_MAX",
    "AsyncOffsetIterator",
    "AsyncPageIterator",
    "OffsetIterator",
    "PageIterator",
]
