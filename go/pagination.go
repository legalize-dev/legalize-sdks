package legalize

import "context"

// PageMax is the server-enforced upper bound on per-page sizes.
const PageMax = 100

// LawsIter lazily iterates over every law that matches a listing or
// search. Call Next until it returns false. After the loop ends, Err
// reports any error encountered mid-stream.
//
// The iterator fetches pages on demand; there are no goroutines or
// buffers to drain, so early exit is cost-free.
type LawsIter struct {
	fetch   func(ctx context.Context, page, perPage int) ([]LawSearchResult, int, error)
	perPage int
	limit   int
	page    int
	// In-progress page buffer + cursor.
	buf       []LawSearchResult
	idx       int
	total     int
	yielded   int
	done      bool
	lastErr   error
	started   bool
	emptyPage bool
}

// NewLawsIter builds an iterator. Exposed for resource helpers;
// callers should reach for LawsService.Iter.
func newLawsIter(
	fetch func(ctx context.Context, page, perPage int) ([]LawSearchResult, int, error),
	perPage int,
	limit int,
) *LawsIter {
	if perPage < 1 || perPage > PageMax {
		perPage = PageMax
	}
	if limit < 0 {
		limit = 0
	}
	return &LawsIter{
		fetch:   fetch,
		perPage: perPage,
		limit:   limit,
		page:    1,
	}
}

// Next advances the iterator by one item. Returns (item, true, nil)
// until exhausted; (zero, false, nil) on normal end; (zero, false,
// err) on any mid-stream error. Safe to call in a for loop:
//
//	for {
//	    law, ok, err := it.Next(ctx)
//	    if err != nil { return err }
//	    if !ok { break }
//	    // ...
//	}
func (it *LawsIter) Next(ctx context.Context) (LawSearchResult, bool, error) {
	if it.done {
		return LawSearchResult{}, false, it.lastErr
	}
	if it.limit > 0 && it.yielded >= it.limit {
		it.done = true
		return LawSearchResult{}, false, nil
	}
	if it.idx >= len(it.buf) {
		if it.emptyPage || (it.started && it.yielded >= it.total && it.total > 0) {
			it.done = true
			return LawSearchResult{}, false, nil
		}
		if it.started && len(it.buf) < it.perPage && len(it.buf) > 0 {
			// Prior page was short; last page already drained.
			it.done = true
			return LawSearchResult{}, false, nil
		}
		items, total, err := it.fetch(ctx, it.page, it.perPage)
		if err != nil {
			it.done = true
			it.lastErr = err
			return LawSearchResult{}, false, err
		}
		it.started = true
		it.buf = items
		it.idx = 0
		it.total = total
		if len(items) == 0 {
			it.emptyPage = true
			it.done = true
			return LawSearchResult{}, false, nil
		}
		it.page++
	}
	item := it.buf[it.idx]
	it.idx++
	it.yielded++
	return item, true, nil
}

// Err returns the last error encountered, if any.
func (it *LawsIter) Err() error { return it.lastErr }

// ReformsIter lazily iterates over reforms for a law. Uses the
// offset/limit pagination the reforms endpoint exposes.
type ReformsIter struct {
	fetch   func(ctx context.Context, batch, offset int) ([]Reform, int, error)
	batch   int
	limit   int
	offset  int
	buf     []Reform
	idx     int
	total   int
	yielded int
	done    bool
	lastErr error
	started bool
}

func newReformsIter(
	fetch func(ctx context.Context, batch, offset int) ([]Reform, int, error),
	batch int,
	limit int,
) *ReformsIter {
	if batch < 1 {
		batch = 100
	}
	if limit < 0 {
		limit = 0
	}
	return &ReformsIter{fetch: fetch, batch: batch, limit: limit}
}

// Next advances the reforms iterator by one item.
func (it *ReformsIter) Next(ctx context.Context) (Reform, bool, error) {
	if it.done {
		return Reform{}, false, it.lastErr
	}
	if it.limit > 0 && it.yielded >= it.limit {
		it.done = true
		return Reform{}, false, nil
	}
	if it.idx >= len(it.buf) {
		if it.started {
			it.offset += len(it.buf)
			if it.offset >= it.total && it.total > 0 {
				it.done = true
				return Reform{}, false, nil
			}
			if len(it.buf) < it.batch && len(it.buf) > 0 {
				it.done = true
				return Reform{}, false, nil
			}
		}
		items, total, err := it.fetch(ctx, it.batch, it.offset)
		if err != nil {
			it.done = true
			it.lastErr = err
			return Reform{}, false, err
		}
		it.started = true
		it.buf = items
		it.idx = 0
		it.total = total
		if len(items) == 0 {
			it.done = true
			return Reform{}, false, nil
		}
	}
	item := it.buf[it.idx]
	it.idx++
	it.yielded++
	return item, true, nil
}

// Err returns the last error encountered.
func (it *ReformsIter) Err() error { return it.lastErr }
