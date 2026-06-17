package legalize

import (
	"context"
	"encoding/xml"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

// ---- Accept negotiation -----------------------------------------------

func TestRequestRaw_DefaultsToXML(t *testing.T) {
	var accept string
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		accept = r.Header.Get("Accept")
		w.Header().Set("Content-Type", "application/xml; charset=utf-8")
		_, _ = w.Write([]byte(`<law id="BOE-A-1978-31229"/>`))
	}))
	res, err := c.RequestRaw(context.Background(), "GET", "/api/v1/es/laws/BOE-A-1978-31229")
	if err != nil {
		t.Fatal(err)
	}
	if accept != "application/xml" {
		t.Errorf("Accept: %q, want application/xml", accept)
	}
	_ = res
}

func TestRequestRaw_FormatJSON(t *testing.T) {
	var accept string
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		accept = r.Header.Get("Accept")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	if _, err := c.RequestRaw(context.Background(), "GET", "/api/v1/countries", WithFormat("json")); err != nil {
		t.Fatal(err)
	}
	if accept != "application/json" {
		t.Errorf("Accept: %q, want application/json", accept)
	}
}

func TestRequestRaw_FormatXMLExplicit(t *testing.T) {
	var accept string
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		accept = r.Header.Get("Accept")
		_, _ = w.Write([]byte(`<ok/>`))
	}))
	if _, err := c.RequestRaw(context.Background(), "GET", "/api/v1/countries", WithFormat("xml")); err != nil {
		t.Fatal(err)
	}
	if accept != "application/xml" {
		t.Errorf("Accept: %q, want application/xml", accept)
	}
}

func TestRequestRaw_ExplicitMediaTypePassthrough(t *testing.T) {
	var accept string
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		accept = r.Header.Get("Accept")
		_, _ = w.Write([]byte(`<ok/>`))
	}))
	if _, err := c.RequestRaw(context.Background(), "GET", "/api/v1/countries", WithFormat("text/xml")); err != nil {
		t.Fatal(err)
	}
	if accept != "text/xml" {
		t.Errorf("Accept: %q, want verbatim text/xml", accept)
	}
}

// ---- options forwarded + auth still present ---------------------------

func TestRequestRaw_ForwardsParamsAndHeadersWithAuth(t *testing.T) {
	var (
		query   string
		trace   string
		auth    string
		accept  string
		apiVers string
	)
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		query = r.URL.Query().Get("per_page")
		trace = r.Header.Get("X-Trace-Id")
		auth = r.Header.Get("Authorization")
		accept = r.Header.Get("Accept")
		apiVers = r.Header.Get("Legalize-Api-Version")
		_, _ = w.Write([]byte(`<ok/>`))
	}))
	h := http.Header{}
	h.Set("X-Trace-Id", "trace-123")
	res, err := c.RequestRaw(context.Background(), "GET", "/api/v1/es/laws",
		WithParams(map[string]any{"per_page": 5}),
		WithExtraHeaders(h),
	)
	if err != nil {
		t.Fatal(err)
	}
	if query != "5" {
		t.Errorf("per_page query: %q", query)
	}
	if trace != "trace-123" {
		t.Errorf("X-Trace-Id: %q", trace)
	}
	// Default SDK headers must still be applied on the raw path.
	if auth != "Bearer leg_test" {
		t.Errorf("Authorization: %q", auth)
	}
	if apiVers != DefaultAPIVersion {
		t.Errorf("Legalize-Api-Version: %q", apiVers)
	}
	// The negotiated Accept (default XML) wins over the JSON default.
	if accept != "application/xml" {
		t.Errorf("Accept: %q", accept)
	}
	_ = res
}

// Caller-set Accept via WithExtraHeaders overrides the WithFormat
// default, mirroring Python where extra_headers is layered last.
func TestRequestRaw_ExtraHeaderAcceptWins(t *testing.T) {
	var accept string
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		accept = r.Header.Get("Accept")
		_, _ = w.Write([]byte(`<ok/>`))
	}))
	h := http.Header{}
	h.Set("Accept", "application/problem+xml")
	if _, err := c.RequestRaw(context.Background(), "GET", "/api/v1/countries", WithExtraHeaders(h)); err != nil {
		t.Fatal(err)
	}
	if accept != "application/problem+xml" {
		t.Errorf("Accept: %q, want caller override", accept)
	}
}

// ---- struct population ------------------------------------------------

func TestRequestRaw_PopulatesStruct(t *testing.T) {
	body := `<law id="BOE-A-1978-31229"><title>Constitución</title></law>`
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/xml; charset=utf-8")
		w.Header().Set("X-Request-Id", "req_raw")
		w.WriteHeader(200)
		_, _ = w.Write([]byte(body))
	}))
	res, err := c.RequestRaw(context.Background(), "GET", "/api/v1/es/laws/BOE-A-1978-31229")
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != 200 {
		t.Errorf("StatusCode: %d", res.StatusCode)
	}
	if string(res.Content) != body {
		t.Errorf("Content: %q", res.Content)
	}
	if res.Text != body {
		t.Errorf("Text: %q", res.Text)
	}
	if res.ContentType != "application/xml; charset=utf-8" {
		t.Errorf("ContentType: %q", res.ContentType)
	}
	if res.Header.Get("X-Request-Id") != "req_raw" {
		t.Errorf("Header X-Request-Id missing: %v", res.Header)
	}

	// The caller is expected to unmarshal Content themselves.
	var law struct {
		ID    string `xml:"id,attr"`
		Title string `xml:"title"`
	}
	if err := xml.Unmarshal(res.Content, &law); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if law.ID != "BOE-A-1978-31229" || law.Title != "Constitución" {
		t.Errorf("parsed: %+v", law)
	}
}

// ---- error path mirrors the JSON path ---------------------------------

func TestRequestRaw_Non2xxReturnsTypedError(t *testing.T) {
	_, c := newTestServer(t, http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/xml")
		w.Header().Set("X-Request-Id", "req_404")
		w.WriteHeader(404)
		_, _ = w.Write([]byte(`<error>not found</error>`))
	}))
	res, err := c.RequestRaw(context.Background(), "GET", "/api/v1/es/laws/MISSING")
	if err == nil {
		t.Fatal("expected error")
	}
	if res != nil {
		t.Errorf("expected nil *RawResponse on error, got %+v", res)
	}
	var nf *NotFoundError
	if !errors.As(err, &nf) {
		t.Fatalf("want NotFoundError, got %T: %v", err, err)
	}
	if nf.RequestID != "req_404" {
		t.Errorf("request id: %q", nf.RequestID)
	}
	// LastResponse is set on the error path, identical to the JSON path.
	lr := c.LastResponse()
	if lr == nil || lr.StatusCode != 404 {
		t.Errorf("LastResponse: %+v", lr)
	}
}

// ---- formatToAccept unit coverage -------------------------------------

func TestFormatToAccept(t *testing.T) {
	cases := map[string]string{
		"":          "application/xml",
		"xml":       "application/xml",
		"XML":       "application/xml",
		"  json  ":  "application/json",
		"json":      "application/json",
		"text/xml":  "text/xml",
		"app/thing": "app/thing",
	}
	for in, want := range cases {
		if got := formatToAccept(in); got != want {
			t.Errorf("formatToAccept(%q) = %q, want %q", in, got, want)
		}
	}
}

// LastResponse must also be set on the success raw path.
func TestRequestRaw_SetsLastResponseOnSuccess(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`<ok/>`))
	}))
	defer srv.Close()
	c, err := New(WithAPIKey("leg_test"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := c.RequestRaw(context.Background(), "GET", "/api/v1/countries"); err != nil {
		t.Fatal(err)
	}
	if lr := c.LastResponse(); lr == nil || lr.StatusCode != 200 {
		t.Errorf("LastResponse: %+v", lr)
	}
}
