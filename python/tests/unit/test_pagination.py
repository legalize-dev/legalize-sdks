"""Pagination iterators — page-based and offset-based."""

from __future__ import annotations

import pytest

from legalize._pagination import (
    PAGE_MAX,
    AsyncOffsetIterator,
    AsyncPageIterator,
    OffsetIterator,
    PageIterator,
)

# ---- PageIterator ------------------------------------------------------


class TestPageIterator:
    def test_single_page(self):
        def fetch(page, per):
            return [1, 2, 3], 3

        assert list(PageIterator(fetch, per_page=50)) == [1, 2, 3]

    def test_multi_page_uses_total(self):
        pages = {1: ([1, 2, 3], 6), 2: ([4, 5, 6], 6), 3: ([], 6)}

        def fetch(page, per):
            return pages[page]

        assert list(PageIterator(fetch, per_page=3)) == [1, 2, 3, 4, 5, 6]

    def test_stops_on_short_page_even_without_total(self):
        pages = {1: ([1, 2, 3], 999), 2: ([4, 5], 999), 3: ([], 999)}
        # per_page=3, page 2 returns 2 items < 3 → stop without calling page 3
        calls = []

        def tracing(page, per):
            calls.append(page)
            return pages[page]

        out = list(PageIterator(tracing, per_page=3))
        assert out == [1, 2, 3, 4, 5]
        assert calls == [1, 2]

    def test_respects_limit(self):
        def fetch(page, per):
            return list(range((page - 1) * per, page * per)), 1000

        assert list(PageIterator(fetch, per_page=10, limit=25)) == list(range(25))

    def test_empty_first_page(self):
        def fetch(page, per):
            return [], 0

        assert list(PageIterator(fetch)) == []

    def test_rejects_invalid_per_page(self):
        with pytest.raises(ValueError, match="per_page"):
            PageIterator(lambda p, s: ([], 0), per_page=0)
        with pytest.raises(ValueError, match="per_page"):
            PageIterator(lambda p, s: ([], 0), per_page=PAGE_MAX + 1)

    def test_rejects_negative_limit(self):
        with pytest.raises(ValueError, match="limit"):
            PageIterator(lambda p, s: ([], 0), limit=-1)

    def test_limit_zero_yields_nothing(self):
        def fetch(page, per):
            return [1, 2, 3], 3

        assert list(PageIterator(fetch, limit=0)) == []


# ---- OffsetIterator ----------------------------------------------------


class TestOffsetIterator:
    def test_multi_batch(self):
        data = list(range(10))
        calls = []

        def fetch(batch, offset):
            calls.append(offset)
            return data[offset : offset + batch], len(data)

        out = list(OffsetIterator(fetch, batch=4))
        assert out == data
        assert calls == [0, 4, 8]

    def test_stops_on_short_batch(self):
        data = list(range(5))

        def fetch(batch, offset):
            return data[offset : offset + batch], 999

        out = list(OffsetIterator(fetch, batch=3))
        assert out == data

    def test_limit(self):
        data = list(range(100))

        def fetch(batch, offset):
            return data[offset : offset + batch], len(data)

        assert list(OffsetIterator(fetch, batch=10, limit=25)) == list(range(25))

    def test_rejects_bad_batch(self):
        with pytest.raises(ValueError, match="batch"):
            OffsetIterator(lambda b, o: ([], 0), batch=0)


# ---- Async counterparts ------------------------------------------------


@pytest.mark.asyncio
class TestAsyncPageIterator:
    async def test_multi_page(self):
        pages = {1: ([1, 2], 4), 2: ([3, 4], 4)}

        async def fetch(page, per):
            return pages[page]

        out = [x async for x in AsyncPageIterator(fetch, per_page=2)]
        assert out == [1, 2, 3, 4]

    async def test_respects_limit(self):
        async def fetch(page, per):
            return list(range((page - 1) * per, page * per)), 1000

        out = [x async for x in AsyncPageIterator(fetch, per_page=10, limit=5)]
        assert out == list(range(5))


@pytest.mark.asyncio
class TestAsyncOffsetIterator:
    async def test_multi_batch(self):
        data = list(range(6))

        async def fetch(batch, offset):
            return data[offset : offset + batch], len(data)

        out = [x async for x in AsyncOffsetIterator(fetch, batch=2)]
        assert out == data
