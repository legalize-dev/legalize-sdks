package legalize

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// newTestServer returns an httptest server + client wired at it. All
// resource tests spin one up, register handler assertions, and tear
// down at t.Cleanup.
func newTestServer(t *testing.T, handler http.Handler) (*httptest.Server, *Client) {
	t.Helper()
	srv := httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	c, err := New(
		WithAPIKey("leg_test"),
		WithBaseURL(srv.URL),
		WithMaxRetries(0),
	)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = c.Close() })
	return srv, c
}

// ---- basic construction + error wiring --------------------------------

func TestNew_RequiresAPIKey(t *testing.T) {
	clearEnv(t)
	_, err := New()
	if err == nil {
		t.Fatal("expected error")
	}
	var ae *AuthenticationError
	if !errors.As(err, &ae) {
		t.Fatalf("want AuthenticationError, got %T", err)
	}
}

func TestNew_AcceptsExplicitKey(t *testing.T) {
	clearEnv(t)
	c, err := New(WithAPIKey("leg_abc"))
	if err != nil {
		t.Fatal(err)
	}
	if c.APIKey() != "leg_abc" {
		t.Error("key")
	}
}

func TestClose_IsNoOp(t *testing.T) {
	c, _ := New(WithAPIKey("leg_abc"))
	if err := c.Close(); err != nil {
		t.Error(err)
	}
}

func TestLastResponse_NilBeforeRequest(t *testing.T) {
	c, _ := New(WithAPIKey("leg_abc"))
	if c.LastResponse() != nil {
		t.Error("want nil")
	}
}

// ---- last_response populated on error ---------------------------------

func TestLastResponse_PopulatedOn404(t *testing.T) {
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Request-Id", "req_abc")
		w.Header().Set("X-Ratelimit-Remaining", "9")
		w.WriteHeader(404)
		_, _ = w.Write([]byte(`{"detail":"not found"}`))
	}))
	_, err := c.Countries().List(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	var nf *NotFoundError
	if !errors.As(err, &nf) {
		t.Fatalf("want NotFoundError, got %T: %v", err, err)
	}
	if nf.RequestID != "req_abc" {
		t.Errorf("request id: %q", nf.RequestID)
	}
	lr := c.LastResponse()
	if lr == nil || lr.StatusCode != 404 {
		t.Errorf("last response: %+v", lr)
	}
	if lr.Header.Get("X-Ratelimit-Remaining") != "9" {
		t.Errorf("headers not preserved")
	}
}

func TestLastResponse_PopulatedOnExhausted429(t *testing.T) {
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Retry-After", "0")
		w.Header().Set("X-Ratelimit-Remaining", "0")
		w.WriteHeader(429)
		_, _ = w.Write([]byte(`{"detail":{"error":"quota_exceeded"}}`))
	}))
	// Bump retries above 0 so we exercise the retry-exhaust path.
	c.retry = RetryPolicy{MaxRetries: 1, InitialDelay: 0, MaxDelay: 0, BackoffFactor: 1}
	_, err := c.Countries().List(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	var rl *RateLimitError
	if !errors.As(err, &rl) {
		t.Fatalf("want RateLimitError, got %T: %v", err, err)
	}
	lr := c.LastResponse()
	if lr == nil || lr.StatusCode != 429 {
		t.Errorf("last response: %+v", lr)
	}
}

// ---- headers on every request -----------------------------------------

func TestUserAgentHeaderFormat(t *testing.T) {
	var captured http.Header
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = r.Header.Clone()
		_, _ = w.Write([]byte(`[]`))
	}))
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	ua := captured.Get("User-Agent")
	if !strings.HasPrefix(ua, "legalize-go/"+Version+" ") {
		t.Errorf("user-agent: %q", ua)
	}
	if !strings.Contains(ua, " go/") {
		t.Errorf("missing go token: %q", ua)
	}
}

func TestAPIVersionHeader_OnEveryRequest(t *testing.T) {
	var count int
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		count++
		if r.Header.Get("Legalize-Api-Version") != DefaultAPIVersion {
			t.Errorf("missing Legalize-Api-Version header: %v", r.Header)
		}
		_, _ = w.Write([]byte(`[]`))
	}))
	for i := 0; i < 3; i++ {
		if _, err := c.Countries().List(context.Background()); err != nil {
			t.Fatal(err)
		}
	}
	if count != 3 {
		t.Errorf("got %d", count)
	}
}

func TestAPIVersionOverride_Propagates(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Get("Legalize-Api-Version")
		_, _ = w.Write([]byte(`[]`))
	}))
	defer srv.Close()
	c, err := New(
		WithAPIKey("leg_test"),
		WithBaseURL(srv.URL),
		WithAPIVersion("v2"),
		WithMaxRetries(0),
	)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	if got != "v2" {
		t.Errorf("got %q", got)
	}
}

func TestAuthorizationBearerFormat(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Get("Authorization")
		_, _ = w.Write([]byte(`[]`))
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_specific"), WithBaseURL(srv.URL), WithMaxRetries(0))
	_, _ = c.Countries().List(context.Background())
	if got != "Bearer leg_specific" {
		t.Errorf("got %q", got)
	}
}

func TestDefaultHeaders_Merged(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Get("X-Custom-Id")
		_, _ = w.Write([]byte(`[]`))
	}))
	defer srv.Close()
	h := http.Header{}
	h.Set("X-Custom-Id", "abc")
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithDefaultHeaders(h), WithMaxRetries(0))
	_, _ = c.Countries().List(context.Background())
	if got != "abc" {
		t.Errorf("default header missing: %q", got)
	}
}

// ---- transport / HTTP error mapping -----------------------------------

func TestConnectionError_WhenBadURL(t *testing.T) {
	c, _ := New(
		WithAPIKey("leg_t"),
		WithBaseURL("http://127.0.0.1:1"), // reserved port, refused
		WithMaxRetries(0),
		WithTimeout(500*time.Millisecond),
	)
	_, err := c.Countries().List(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	var ce *APIConnectionError
	if !errors.As(err, &ce) {
		t.Fatalf("want APIConnectionError, got %T: %v", err, err)
	}
}

func TestTimeoutError_OnContextDeadline(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		_, _ = w.Write([]byte(`[]`))
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	_, err := c.Countries().List(ctx)
	if err == nil {
		t.Fatal("expected error")
	}
	var te *APITimeoutError
	if !errors.As(err, &te) {
		t.Fatalf("want APITimeoutError, got %T: %v", err, err)
	}
}

// ---- Do raw escape hatch ----------------------------------------------

func TestDo_ReturnsRawResponseAndBody(t *testing.T) {
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Totally-Custom", "yes")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	resp, body, err := c.Do(context.Background(), "GET", "/api/v1/custom")
	if err != nil {
		t.Fatal(err)
	}
	if resp.Header.Get("X-Totally-Custom") != "yes" {
		t.Error("header")
	}
	var v struct{ OK bool }
	if err := json.Unmarshal(body, &v); err != nil {
		t.Fatal(err)
	}
	if !v.OK {
		t.Error("body")
	}
}

func TestDo_Post_NotRetried(t *testing.T) {
	var attempts int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		w.Header().Set("Retry-After", "0")
		w.WriteHeader(500)
		_, _ = w.Write([]byte(`{"detail":"boom"}`))
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(3))
	_, _, err := c.Do(context.Background(), http.MethodPost, "/api/v1/custom", WithJSONBody(map[string]any{"k": "v"}))
	if err == nil {
		t.Fatal("expected error")
	}
	// POST is NOT idempotent by default — exactly one call.
	if attempts != 1 {
		t.Errorf("attempts: %d (POST must not retry)", attempts)
	}
}

func TestDo_Get_RetriedOn500(t *testing.T) {
	var attempts int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 3 {
			w.WriteHeader(500)
			_, _ = io.WriteString(w, `{"detail":"boom"}`)
			return
		}
		w.WriteHeader(200)
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(
		WithAPIKey("leg_t"),
		WithBaseURL(srv.URL),
		WithRetryPolicy(RetryPolicy{MaxRetries: 5, InitialDelay: 0, MaxDelay: 0, BackoffFactor: 1}),
	)
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	if attempts != 3 {
		t.Errorf("attempts: %d", attempts)
	}
}
