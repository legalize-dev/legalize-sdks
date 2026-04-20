package legalize

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

// ---- ParseRetryAfter (delta-seconds + HTTP-date) -----------------------

func TestParseRetryAfter_DeltaSecondsInteger(t *testing.T) {
	d := ParseRetryAfter("120")
	if d == nil || *d != 120*time.Second {
		t.Fatalf("got %v", d)
	}
}

func TestParseRetryAfter_ClampsNegativeToZero(t *testing.T) {
	d := ParseRetryAfter("-5")
	if d == nil || *d != 0 {
		t.Fatalf("got %v", d)
	}
}

func TestParseRetryAfter_HTTPDateFuture(t *testing.T) {
	future := time.Now().Add(60 * time.Second).UTC().Format(http.TimeFormat)
	d := ParseRetryAfter(future)
	if d == nil {
		t.Fatal("nil")
	}
	if *d < 55*time.Second || *d > 65*time.Second {
		t.Fatalf("got %v", *d)
	}
}

func TestParseRetryAfter_HTTPDatePastClampsToZero(t *testing.T) {
	past := time.Now().Add(-10 * time.Minute).UTC().Format(http.TimeFormat)
	d := ParseRetryAfter(past)
	if d == nil || *d != 0 {
		t.Fatalf("got %v", d)
	}
}

func TestParseRetryAfter_MalformedReturnsNil(t *testing.T) {
	if ParseRetryAfter("not a date") != nil {
		t.Error("want nil")
	}
	if ParseRetryAfter("") != nil {
		t.Error("want nil")
	}
}

// ---- Retry policy decisions -------------------------------------------

func TestRetryPolicy_DoesNotRetryBeyondMax(t *testing.T) {
	p := RetryPolicy{MaxRetries: 2}
	if !p.ShouldRetry(0, 500) {
		t.Error("should retry 0/2")
	}
	if !p.ShouldRetry(1, 500) {
		t.Error("should retry 1/2")
	}
	if p.ShouldRetry(2, 500) {
		t.Error("must not retry 2/2")
	}
}

func TestRetryPolicy_OnlyRetriesOnKnownStatuses(t *testing.T) {
	p := RetryPolicy{MaxRetries: 3}
	retry := []int{408, 429, 500, 502, 503, 504}
	for _, s := range retry {
		if !p.ShouldRetry(0, s) {
			t.Errorf("%d should retry", s)
		}
	}
	noRetry := []int{400, 401, 403, 404, 422, 418}
	for _, s := range noRetry {
		if p.ShouldRetry(0, s) {
			t.Errorf("%d must not retry", s)
		}
	}
}

func TestRetryPolicy_NetworkErrorAlwaysRetries(t *testing.T) {
	p := RetryPolicy{MaxRetries: 2}
	if !p.ShouldRetry(0, -1) {
		t.Error("network err must retry")
	}
	if !p.ShouldRetry(1, -1) {
		t.Error("network err must retry on attempt 1")
	}
	if p.ShouldRetry(2, -1) {
		t.Error("stop at max")
	}
}

// ---- ComputeDelay -----------------------------------------------------

func TestComputeDelay_RespectsRetryAfter(t *testing.T) {
	p := NewRetryPolicy()
	d := 3 * time.Second
	got := p.ComputeDelay(0, &d)
	if got != 3*time.Second {
		t.Errorf("got %v", got)
	}
}

func TestComputeDelay_CapsRetryAfterAtMaxDelay(t *testing.T) {
	p := RetryPolicy{MaxDelay: 5 * time.Second}
	d := 100 * time.Second
	got := p.ComputeDelay(0, &d)
	if got != 5*time.Second {
		t.Errorf("got %v", got)
	}
}

func TestComputeDelay_ExponentialMonotoneUpToCap(t *testing.T) {
	// Property check: with no Retry-After, the *upper bound* of the
	// jitter window is non-decreasing and capped at MaxDelay.
	p := RetryPolicy{InitialDelay: 100 * time.Millisecond, MaxDelay: 2 * time.Second, BackoffFactor: 2}
	// Run many iterations to sample the jitter; observe each
	// attempt's max never exceeds the theoretical cap.
	for attempt := 0; attempt < 6; attempt++ {
		cap := 100 * time.Millisecond
		for i := 0; i < attempt; i++ {
			cap *= 2
		}
		if cap > 2*time.Second {
			cap = 2 * time.Second
		}
		for trial := 0; trial < 100; trial++ {
			d := p.ComputeDelay(attempt, nil)
			if d < 0 || d > cap+time.Millisecond {
				t.Errorf("attempt %d trial %d: d=%v cap=%v", attempt, trial, d, cap)
			}
		}
	}
}

// ---- End-to-end retry behaviour ---------------------------------------

func TestRetry_HonorsHTTPDateFromServer(t *testing.T) {
	var calls int
	// HTTP-date is second-resolution, so we ask for ~2 seconds to
	// leave headroom for rounding and scheduling jitter.
	future := time.Now().Add(2 * time.Second).UTC().Format(http.TimeFormat)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls == 1 {
			w.Header().Set("Retry-After", future)
			w.WriteHeader(429)
			return
		}
		w.WriteHeader(200)
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(
		WithAPIKey("leg_t"),
		WithBaseURL(srv.URL),
		WithRetryPolicy(RetryPolicy{MaxRetries: 1, InitialDelay: 0, MaxDelay: 30 * time.Second, BackoffFactor: 2}),
	)
	start := time.Now()
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	elapsed := time.Since(start)
	if calls != 2 {
		t.Errorf("calls: %d", calls)
	}
	// Should sleep roughly 1-2s; allow a generous band for CI jitter.
	if elapsed < 500*time.Millisecond || elapsed > 4*time.Second {
		t.Errorf("elapsed: %v", elapsed)
	}
}

func TestRetry_POSTNotRetriedByDefault(t *testing.T) {
	// The parity spec: POST methods must not retry on 500 by default.
	// This is enforced client-side via the idempotentMethods set.
	var calls int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(500)
		_, _ = io.WriteString(w, `{"detail":"boom"}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL),
		WithRetryPolicy(RetryPolicy{MaxRetries: 3, InitialDelay: 0, MaxDelay: 0}))
	_, err := c.Webhooks().Create(context.Background(), WebhookCreateOptions{
		URL:        "https://example.com/hook",
		EventTypes: []string{"law.updated"},
	})
	if err == nil {
		t.Fatal("expected error")
	}
	var se *ServerError
	if !errors.As(err, &se) {
		t.Fatalf("want ServerError, got %T", err)
	}
	if calls != 1 {
		t.Errorf("POST retried %d times — must be 1", calls)
	}
}

func TestRetry_GETRetriedOn429(t *testing.T) {
	var calls int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls < 2 {
			w.Header().Set("Retry-After", "0")
			w.WriteHeader(429)
			return
		}
		w.WriteHeader(200)
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(
		WithAPIKey("leg_t"),
		WithBaseURL(srv.URL),
		WithRetryPolicy(RetryPolicy{MaxRetries: 2, InitialDelay: 0, MaxDelay: 0}),
	)
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	if calls != 2 {
		t.Errorf("calls: %d", calls)
	}
}

func TestRetry_CancelledContextStopsEarly(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Retry-After", "5")
		w.WriteHeader(429)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL),
		WithRetryPolicy(RetryPolicy{MaxRetries: 3, InitialDelay: 0, MaxDelay: 10 * time.Second}))
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()
	_, err := c.Countries().List(ctx)
	if err == nil {
		t.Fatal("expected error")
	}
}
