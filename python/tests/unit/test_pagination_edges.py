"""Edge cases in async iterators + offset iterator validation."""

from __future__ import annotations

import pytest

from legalize._pagination import (
    PAGE_MAX,
    AsyncOffsetIterator,
    AsyncPageIterator,
    OffsetIterator,
)

# Invalid args -----------------------------------------------------------


class TestAsyncPageIteratorValidation:
    def test_rejects_bad_per_page(self):
        with pytest.raises(ValueError, match="per_page"):
            AsyncPageIterator(lambda p, s: ([], 0), per_page=0)

    def test_rejects_above_max(self):
        with pytest.raises(ValueError, match="per_page"):
            AsyncPageIterator(lambda p, s: ([], 0), per_page=PAGE_MAX + 1)

    def test_rejects_negative_limit(self):
        with pytest.raises(ValueError, match="limit"):
            AsyncPageIterator(lambda p, s: ([], 0), limit=-1)


class TestAsyncOffsetIteratorValidation:
    def test_rejects_bad_batch(self):
        with pytest.raises(ValueError, match="batch"):
            AsyncOffsetIterator(lambda b, o: ([], 0), batch=0)

    def test_rejects_negative_limit(self):
        with pytest.raises(ValueError, match="limit"):
            AsyncOffsetIterator(lambda b, o: ([], 0), limit=-1)


class TestOffsetIteratorValidation:
    def test_rejects_negative_limit(self):
        with pytest.raises(ValueError, match="limit"):
            OffsetIterator(lambda b, o: ([], 0), limit=-1)


# Empty / limit=0 / short page edge cases -------------------------------


@pytest.mark.asyncio
class TestAsyncPageEmpty:
    async def test_empty_first_page(self):
        async def fetch(page, per):
            return [], 0

        out = [x async for x in AsyncPageIterator(fetch)]
        assert out == []

    async def test_limit_zero_yields_nothing(self):
        async def fetch(page, per):
            return [1, 2, 3], 3

        out = [x async for x in AsyncPageIterator(fetch, limit=0)]
        assert out == []

    async def test_stops_on_short_page(self):
        pages = {1: ([1, 2], 999), 2: ([3], 999)}

        async def fetch(page, per):
            return pages[page]

        out = [x async for x in AsyncPageIterator(fetch, per_page=2)]
        assert out == [1, 2, 3]


@pytest.mark.asyncio
class TestAsyncOffsetEdge:
    async def test_empty(self):
        async def fetch(b, o):
            return [], 0

        out = [x async for x in AsyncOffsetIterator(fetch, batch=3)]
        assert out == []

    async def test_limit_zero(self):
        async def fetch(b, o):
            return [1, 2, 3], 3

        out = [x async for x in AsyncOffsetIterator(fetch, batch=3, limit=0)]
        assert out == []

    async def test_stops_on_short_batch(self):
        data = [1, 2, 3]

        async def fetch(b, o):
            return data[o : o + b], 999

        out = [x async for x in AsyncOffsetIterator(fetch, batch=5)]
        assert out == data
