package legalize

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strconv"
	"testing"
)

func makeResults(prefix string, n int) []LawSearchResult {
	out := make([]LawSearchResult, n)
	for i := 0; i < n; i++ {
		out[i] = LawSearchResult{
			ID:      fmt.Sprintf("%s_%d", prefix, i),
			Title:   "T",
			Country: "es",
			LawType: "ley",
		}
	}
	return out
}

// ---- edge case: total=0 yields nothing --------------------------------

func TestLawsIter_TotalZeroYieldsNothing(t *testing.T) {
	requests := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		resp := PaginatedLaws{
			Country: "es",
			Total:   0,
			Page:    1,
			PerPage: 50,
			Results: []LawSearchResult{},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 50, 0, nil)
	count := 0
	for {
		_, ok, err := it.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			break
		}
		count++
	}
	if count != 0 {
		t.Errorf("count: %d", count)
	}
	if requests > 1 {
		t.Errorf("requests: %d — must not spin", requests)
	}
}

// ---- iter exhausts exactly `total` across page boundaries -------------

func TestLawsIter_ExhaustsAcrossPageBoundaries(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		page, _ := strconv.Atoi(r.URL.Query().Get("page"))
		perPage, _ := strconv.Atoi(r.URL.Query().Get("per_page"))
		total := 7
		start := (page - 1) * perPage
		end := start + perPage
		if end > total {
			end = total
		}
		n := end - start
		if n < 0 {
			n = 0
		}
		resp := PaginatedLaws{
			Country: "es",
			Total:   total,
			Page:    page,
			PerPage: perPage,
			Results: makeResults(fmt.Sprintf("p%d", page), n),
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 3, 0, nil)
	collected := 0
	for {
		_, ok, err := it.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			break
		}
		collected++
		if collected > 100 {
			t.Fatal("runaway")
		}
	}
	if collected != 7 {
		t.Errorf("collected %d, want 7", collected)
	}
}

// ---- limit caps iteration --------------------------------------------

func TestLawsIter_RespectsLimit(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := PaginatedLaws{
			Country: "es",
			Total:   100,
			Page:    1,
			PerPage: 50,
			Results: makeResults("p", 50),
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 50, 3, nil)
	collected := 0
	for {
		_, ok, err := it.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			break
		}
		collected++
	}
	if collected != 3 {
		t.Errorf("collected %d, want 3", collected)
	}
}

// ---- error mid-iteration surfaces ------------------------------------

func TestLawsIter_PropagatesErrorMidStream(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls == 1 {
			resp := PaginatedLaws{
				Country: "es", Total: 20, Page: 1, PerPage: 5,
				Results: makeResults("p", 5),
			}
			_ = json.NewEncoder(w).Encode(resp)
			return
		}
		w.WriteHeader(500)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 5, 0, nil)
	// Drain the first page.
	for i := 0; i < 5; i++ {
		_, ok, err := it.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			t.Fatal("exhausted too early")
		}
	}
	// Next call triggers the 500.
	_, _, err := it.Next(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
}

// ---- reforms iterator ------------------------------------------------

func TestReformsIter_ExhaustsViaOffset(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		offset, _ := strconv.Atoi(r.URL.Query().Get("offset"))
		limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
		total := 6
		end := offset + limit
		if end > total {
			end = total
		}
		n := end - offset
		if n < 0 {
			n = 0
		}
		reforms := make([]Reform, n)
		for i := 0; i < n; i++ {
			reforms[i] = Reform{Date: "2024-01-01"}
		}
		resp := ReformsResponse{
			LawID: "L", Total: total, Offset: offset, Limit: limit, Reforms: reforms,
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Reforms().Iter(context.Background(), "es", "L", 2, 0)
	n := 0
	for {
		_, ok, err := it.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			break
		}
		n++
		if n > 100 {
			t.Fatal("runaway")
		}
	}
	if n != 6 {
		t.Errorf("got %d", n)
	}
}

func TestReformsIter_TotalZero(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := ReformsResponse{LawID: "L", Total: 0, Offset: 0, Limit: 100, Reforms: []Reform{}}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Reforms().Iter(context.Background(), "es", "L", 100, 0)
	_, ok, err := it.Next(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Error("must not yield anything")
	}
}
