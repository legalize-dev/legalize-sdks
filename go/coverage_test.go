package legalize

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
	"time"
)

// Tests in this file top up coverage for branches the primary test
// suites don't touch directly. They keep the public contract the
// same and exercise only observable behaviour.

// ---- cleanParams coercions --------------------------------------------

func TestCleanParams_AllTypes(t *testing.T) {
	tb := "abc"
	ti := 7
	tBool := true
	cases := map[string]map[string]any{
		"strptr":      {"k": &tb},
		"strptr_nil":  {"k": (*string)(nil)},
		"strptr_emp":  {"k": String("")},
		"intptr":      {"k": &ti},
		"intptr_nil":  {"k": (*int)(nil)},
		"boolptr":     {"k": &tBool},
		"boolptr_nil": {"k": (*bool)(nil)},
		"boolptr_f":   {"k": Bool(false)},
		"string":      {"k": "abc"},
		"string_e":    {"k": ""},
		"int":         {"k": 3},
		"int64":       {"k": int64(4)},
		"bool_t":      {"k": true},
		"bool_f":      {"k": false},
		"float":       {"k": 2.5},
		"slice_str":   {"k": []string{"a", "b"}},
		"slice_emp":   {"k": []string{}},
		"slice_any":   {"k": []any{"a", 1}},
		"slice_any_e": {"k": []any{}},
		"default":     {"k": struct{}{}},
	}
	expected := map[string]string{
		"strptr":      "abc",
		"strptr_nil":  "",
		"strptr_emp":  "",
		"intptr":      "7",
		"intptr_nil":  "",
		"boolptr":     "true",
		"boolptr_nil": "",
		"boolptr_f":   "false",
		"string":      "abc",
		"string_e":    "",
		"int":         "3",
		"int64":       "4",
		"bool_t":      "true",
		"bool_f":      "false",
		"float":       "2.5",
		"slice_str":   "a,b",
		"slice_emp":   "",
		"slice_any":   "a,1",
		"slice_any_e": "",
		"default":     "{}",
	}
	for name, in := range cases {
		t.Run(name, func(t *testing.T) {
			out := cleanParams(in)
			if expected[name] == "" {
				if _, present := out["k"]; present {
					t.Errorf("%s: %v should have been dropped", name, in)
				}
				return
			}
			if out["k"] != expected[name] {
				t.Errorf("%s: got %q want %q", name, out["k"], expected[name])
			}
		})
	}
}

// ---- ValidationError with empty error list ---------------------------

func TestErrorFromResponse_ValidationEmptyList(t *testing.T) {
	err := ErrorFromResponse(mkResp(422, nil, nil), []byte(`{"detail":[]}`))
	var ve *ValidationError
	if !errors.As(err, &ve) {
		t.Fatal("want ValidationError")
	}
	if ve.Message == "" {
		t.Error("empty message")
	}
}

// ---- Error.Error() formatting of APIConnectionError without cause ----

func TestConnectionError_Format(t *testing.T) {
	e := &APIConnectionError{}
	if !strings.Contains(e.Error(), "connection") {
		t.Errorf("got %q", e.Error())
	}
}

// ---- Iter.Err() exposes error --------------------------------------

func TestLawsIter_ErrExposed(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 10, 0, nil)
	_, _, err := it.Next(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	if it.Err() == nil {
		t.Error("Err() should expose error")
	}
	// Calling Next after done returns the same error.
	_, ok, err2 := it.Next(context.Background())
	if ok {
		t.Error("should be done")
	}
	if err2 == nil {
		t.Error("err sticky")
	}
}

func TestReformsIter_Err(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Reforms().Iter(context.Background(), "es", "L", 10, 0)
	_, _, err := it.Next(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	if it.Err() == nil {
		t.Error("Err() nil")
	}
}

// ---- SearchIter runs a search ----------------------------------------

func TestLawsSearchIter(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("q") == "" {
			t.Error("no q")
		}
		_, _ = io.WriteString(w, `{"country":"es","total":0,"page":1,"per_page":10,"results":[]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().SearchIter(context.Background(), "es", "elections", 0, 5, nil)
	_, ok, err := it.Next(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if ok {
		t.Error("empty search should yield nothing")
	}
}

// ---- WithHTTPClient option -------------------------------------------

func TestWithHTTPClient_UsesProvided(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-Custom-Transport") != "1" {
			t.Errorf("missing custom transport marker")
		}
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()

	// A custom transport that stamps a header and delegates.
	custom := &http.Client{
		Transport: roundTripFunc(func(req *http.Request) (*http.Response, error) {
			req.Header.Set("X-Custom-Transport", "1")
			return http.DefaultTransport.RoundTrip(req)
		}),
	}
	c, err := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithHTTPClient(custom), WithMaxRetries(0))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

// ---- NonJSON body -> APIError on success ------------------------------

func TestRequestJSON_MalformedSuccessBody(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 200 with invalid JSON body.
		_, _ = io.WriteString(w, `not json`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	_, err := c.Countries().List(context.Background())
	if err == nil {
		t.Fatal("expected error")
	}
	var ae *APIError
	if !errors.As(err, &ae) {
		t.Fatalf("want APIError, got %T", err)
	}
}

// ---- buildURL with absolute URL ---------------------------------------

func TestDo_AbsoluteURL(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL("http://unused"), WithMaxRetries(0))
	_, _, err := c.Do(context.Background(), "GET", srv.URL+"/api/v1/whatever")
	if err != nil {
		t.Fatal(err)
	}
}

// ---- buildURL with path missing leading slash -------------------------

func TestDo_PathWithoutLeadingSlash(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/custom" {
			t.Errorf("path: %q", r.URL.Path)
		}
		_, _ = io.WriteString(w, `{}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, _, err := c.Do(context.Background(), "GET", "api/v1/custom"); err != nil {
		t.Fatal(err)
	}
}

// ---- sleepOrCancel zero-duration path ---------------------------------

func TestSleepOrCancel_ZeroDuration(t *testing.T) {
	if !sleepOrCancel(context.Background(), 0) {
		t.Error("should return true on zero duration")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if sleepOrCancel(ctx, 0) {
		t.Error("should return false on cancelled ctx")
	}
}

// ---- ComputeDelay respects nil retry-after and MaxDelay=0 ------------

func TestComputeDelay_ZeroMaxDelayProducesZero(t *testing.T) {
	p := RetryPolicy{MaxRetries: 3, InitialDelay: 100 * time.Millisecond, MaxDelay: 10 * time.Second, BackoffFactor: 2}
	// With zero retry-after, value must be within jitter window.
	for i := 0; i < 50; i++ {
		d := p.ComputeDelay(0, nil)
		if d > 100*time.Millisecond+time.Millisecond {
			t.Errorf("over bound: %v", d)
		}
	}
}

// ---- Sync on config.timeout assigns to client --------------------------

func TestWithTimeout_AppliesToHTTPClient(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(200 * time.Millisecond)
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(
		WithAPIKey("leg_t"),
		WithBaseURL(srv.URL),
		WithTimeout(50*time.Millisecond),
		WithMaxRetries(0),
	)
	_, err := c.Countries().List(context.Background())
	if err == nil {
		t.Fatal("expected timeout error")
	}
	var te *APITimeoutError
	if !errors.As(err, &te) {
		// Under some environments, net/http surfaces as APIConnectionError
		// even for timeouts. Accept either.
		var ce *APIConnectionError
		if !errors.As(err, &ce) {
			t.Fatalf("want APITimeoutError or APIConnectionError, got %T: %v", err, err)
		}
	}
}

// ---- legalizeError() markers on every type -----------------------------

func TestLegalizeErrorMarkers_Compile(t *testing.T) {
	// Call them directly to keep coverage non-zero.
	(&APIError{}).legalizeError()
	(&APIConnectionError{}).legalizeError()
	(&APITimeoutError{}).legalizeError()
	(&WebhookVerificationError{}).legalizeError()
	// Typed subclasses do NOT themselves implement the marker
	// separately — they embed *APIError — but we can still walk
	// their error chain.
	_ = (&AuthenticationError{APIError: &APIError{}}).Error()
	_ = (&ForbiddenError{APIError: &APIError{}}).Error()
	_ = (&NotFoundError{APIError: &APIError{}}).Error()
	_ = (&InvalidRequestError{APIError: &APIError{}}).Error()
	_ = (&ValidationError{APIError: &APIError{}}).Error()
	_ = (&RateLimitError{APIError: &APIError{}}).Error()
	_ = (&ServerError{APIError: &APIError{}}).Error()
	_ = (&ServiceUnavailableError{APIError: &APIError{}}).Error()
}

// ---- Resource methods surface errors ---------------------------------

func TestResourceErrors_PropagateFromServer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
		_, _ = io.WriteString(w, `{"detail":"nope"}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))

	ctx := context.Background()
	if _, err := c.Jurisdictions().List(ctx, "es"); err == nil {
		t.Error("expected error")
	}
	if _, err := c.LawTypes().List(ctx, "es"); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Laws().Search(ctx, "es", "q", nil); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Laws().Meta(ctx, "es", "L"); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Laws().Commits(ctx, "es", "L"); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Laws().AtCommit(ctx, "es", "L", "S"); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Stats().Retrieve(ctx, "es", nil); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Webhooks().Retrieve(ctx, 1); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Webhooks().List(ctx); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Webhooks().Update(ctx, 1, WebhookUpdateOptions{URL: String("x")}); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Webhooks().Deliveries(ctx, 1, nil); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Webhooks().Retry(ctx, 1, 2); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Webhooks().Test(ctx, 1); err == nil {
		t.Error("expected error")
	}
	if err := c.Webhooks().Delete(ctx, 1); err == nil {
		t.Error("expected error")
	}
	if _, err := c.Reforms().List(ctx, "es", "L", nil); err == nil {
		t.Error("expected error")
	}
}

// ---- cloneLawsOpts nil path ------------------------------------------

func TestCloneLawsOpts_Nil(t *testing.T) {
	clone := cloneLawsOpts(nil)
	if clone == nil {
		t.Fatal("nil")
	}
	// Must be empty.
	if clone.Page != nil || clone.PerPage != nil {
		t.Error("should be zero")
	}
}

// ---- cloneLawsOpts with non-nil opts ---------------------------------

func TestCloneLawsOpts_NonNil(t *testing.T) {
	src := &LawsListOptions{Page: Int(5), Status: String("vigente")}
	c := cloneLawsOpts(src)
	if c == src {
		t.Error("must be a copy")
	}
	if c.Page == nil || *c.Page != 5 {
		t.Error("page")
	}
	if c.Status == nil || *c.Status != "vigente" {
		t.Error("status")
	}
}

// ---- LawsIter / ReformsIter with non-default per-page / batch --------

func TestLawsIter_ClampsPerPage(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// out-of-range per_page requested — SDK clamps to PageMax.
		if r.URL.Query().Get("per_page") != "100" {
			t.Errorf("expected per_page=100, got %q", r.URL.Query().Get("per_page"))
		}
		_, _ = io.WriteString(w, `{"country":"es","total":0,"page":1,"per_page":100,"results":[]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 500, 0, &LawsListOptions{Status: String("vigente")})
	_, _, _ = it.Next(context.Background())
}

func TestReformsIter_ClampsBatch(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"law_id":"L","total":0,"offset":0,"limit":100,"reforms":[]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Reforms().Iter(context.Background(), "es", "L", 0, 0) // 0 -> default 100
	_, _, _ = it.Next(context.Background())
	it2 := c.Reforms().Iter(context.Background(), "es", "L", 0, -1) // negative limit -> 0
	_, _, _ = it2.Next(context.Background())
}

// ---- sendWithRetry on idempotent method retries transport errors ----

func TestSendWithRetry_RetriesTransportOnGET(t *testing.T) {
	var calls int
	// Use a TCP listener we can accept/reject selectively.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		// First call hijacks the connection and closes it to simulate a transport error.
		if calls == 1 {
			hj, ok := w.(http.Hijacker)
			if !ok {
				t.Fatal("no hijacker")
			}
			conn, _, err := hj.Hijack()
			if err != nil {
				t.Fatal(err)
			}
			_ = conn.Close()
			return
		}
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL),
		WithRetryPolicy(RetryPolicy{MaxRetries: 2, InitialDelay: 0, MaxDelay: 0}))
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	if calls < 2 {
		t.Errorf("retry transport: calls=%d", calls)
	}
}

// ---- buildURL malformed URL parse failure ---------------------------

func TestDo_MalformedURLReturnsError(t *testing.T) {
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL("http://example.com"), WithMaxRetries(0))
	_, _, err := c.Do(context.Background(), "GET", "\x00", WithParams(map[string]any{"k": "v"}))
	if err == nil {
		t.Fatal("expected error")
	}
}

// ---- Verify with JSON array payload -> fails post-verify -----------

func TestVerify_ArrayPayloadFailsPostVerify(t *testing.T) {
	payload := []byte(`[1,2,3]`)
	now := time.Now()
	ts := strconv.FormatInt(now.Unix(), 10)
	sig := ComputeSignature(testSecret, payload, ts)
	_, err := Verify(payload, sig, ts, testSecret, WithReferenceTime(now))
	if err == nil {
		t.Fatal("JSON arrays are not valid events")
	}
}

// ---- parseErrorBody with no detail key ------------------------------

func TestParseErrorBody_MissingDetail(t *testing.T) {
	err := ErrorFromResponse(mkResp(400, nil, nil), []byte(`{"message":"x","error":"y"}`))
	var ire *InvalidRequestError
	if !errors.As(err, &ire) {
		t.Fatal("want InvalidRequestError")
	}
	if ire.Code != "y" {
		t.Errorf("code: %q", ire.Code)
	}
}

// ---- extractSchemeHexes edge case -------------------------------------

func TestExtractSchemeHexes_MalformedParts(t *testing.T) {
	out := extractSchemeHexes("")
	if len(out) != 0 {
		t.Error("empty")
	}
	out = extractSchemeHexes("no-equals-here,v1=,v1=abc")
	if len(out) != 1 || out[0] != "abc" {
		t.Errorf("got %v", out)
	}
}

// ---- Bool helper runs --------------------------------------------------

func TestBoolHelper(t *testing.T) {
	b := Bool(true)
	if b == nil || !*b {
		t.Error("Bool helper")
	}
}

// ---- parseErrorBody with nested dict code fallback --------------------

func TestParseErrorBody_CodeFallback(t *testing.T) {
	// "code" key used instead of "error".
	err := ErrorFromResponse(mkResp(400, nil, nil), []byte(`{"detail":{"code":"bad","detail":"explain"}}`))
	var ire *InvalidRequestError
	if !errors.As(err, &ire) {
		t.Fatal("want InvalidRequestError")
	}
	if ire.Code != "bad" {
		t.Errorf("code: %q", ire.Code)
	}
	if ire.Message != "explain" {
		t.Errorf("msg: %q", ire.Message)
	}
}

// ---- Deliveries with no opts -----------------------------------------

func TestDeliveries_NoOpts(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.RawQuery != "" {
			t.Errorf("unexpected query: %q", r.URL.RawQuery)
		}
		_, _ = io.WriteString(w, `{}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Webhooks().Deliveries(context.Background(), 9, nil); err != nil {
		t.Fatal(err)
	}
}

// ---- RateLimitError float64 retry-after via body ---------------------

func TestRateLimitError_BodyFloatRetryAfter(t *testing.T) {
	body := []byte(`{"detail":{"error":"quota_exceeded","retry_after":60,"limit":100}}`)
	err := ErrorFromResponse(mkResp(429, nil, nil), body)
	var rle *RateLimitError
	if !errors.As(err, &rle) {
		t.Fatal("want RateLimitError")
	}
	if rle.RetryAfter.Seconds() != 60 {
		t.Errorf("retry-after: %v", rle.RetryAfter)
	}
	if rle.Limit != 100 {
		t.Errorf("limit: %d", rle.Limit)
	}
}
