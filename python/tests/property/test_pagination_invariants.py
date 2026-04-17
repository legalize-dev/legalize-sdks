"""Property-based tests for pagination iterators.

Invariants:

1. **No duplication**: iterating never yields the same item twice.
2. **No omission**: the iterator yields exactly ``min(total, limit)``
   items (all items if ``limit`` is None).
3. **In order**: items are yielded in the server's order (each page is
   appended after the previous).
4. **Short-page early stop**: a page shorter than per_page ends iteration
   even if total claims more items.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from legalize._pagination import OffsetIterator, PageIterator


@given(
    total=st.integers(min_value=0, max_value=500),
    per_page=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100, deadline=None)
def test_page_iterator_returns_exactly_total(total, per_page):
    data = list(range(total))

    def fetch(page, per):
        offset = (page - 1) * per
        return data[offset : offset + per], total

    out = list(PageIterator(fetch, per_page=per_page))
    assert out == data
    assert len(out) == total


@given(
    total=st.integers(min_value=0, max_value=200),
    per_page=st.integers(min_value=1, max_value=50),
    limit=st.integers(min_value=0, max_value=200),
)
@settings(max_examples=100, deadline=None)
def test_page_iterator_respects_limit(total, per_page, limit):
    data = list(range(total))

    def fetch(page, per):
        offset = (page - 1) * per
        return data[offset : offset + per], total

    out = list(PageIterator(fetch, per_page=per_page, limit=limit))
    assert out == data[: min(total, limit)]


@given(
    total=st.integers(min_value=0, max_value=500),
    batch=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=100, deadline=None)
def test_offset_iterator_returns_exactly_total(total, batch):
    data = list(range(total))

    def fetch(size, offset):
        return data[offset : offset + size], total

    out = list(OffsetIterator(fetch, batch=batch))
    assert out == data


@given(
    items=st.lists(st.integers(min_value=0, max_value=10_000), min_size=0, max_size=100, unique=True),
    per_page=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=100, deadline=None)
def test_no_duplicates(items, per_page):
    data = items[:]
    total = len(data)

    def fetch(page, per):
        offset = (page - 1) * per
        return data[offset : offset + per], total

    seen = set()
    for item in PageIterator(fetch, per_page=per_page):
        assert item not in seen
        seen.add(item)


@given(
    data=st.data(),
)
@settings(max_examples=50, deadline=None)
def test_short_page_stops_iteration(data):
    """Server lies about total and returns a short page → stop.

    Constraint: ``total >= per_page`` so a "short" page is genuinely
    shorter than per_page (otherwise "short" is just the final page).
    """
    per_page = data.draw(st.integers(min_value=2, max_value=20))
    total = data.draw(st.integers(min_value=per_page, max_value=200))
    dataset = list(range(total))
    early_cutoff = per_page - 1  # always < per_page → a genuine short page

    def fetch(page, per):
        offset = (page - 1) * per
        chunk = dataset[offset : offset + per]
        if page == 1:
            # Short first page; claim ``total`` items exist.
            return chunk[:early_cutoff], total
        return chunk, total

    out = list(PageIterator(fetch, per_page=per_page))
    assert len(out) == early_cutoff
