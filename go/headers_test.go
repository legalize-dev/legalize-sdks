package legalize

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"runtime"
	"strings"
	"testing"
)

// These tests pin the shape of every outgoing header the SDK is
// supposed to send. Parity with Python's test_audit_fixes.py.

func TestHeaders_UserAgentIncludesOS(t *testing.T) {
	var captured string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = r.Header.Get("User-Agent")
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Countries().List(context.Background()); err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(captured, " "+runtime.GOOS) {
		t.Errorf("user-agent missing GOOS: %q", captured)
	}
}

func TestHeaders_AcceptJSON(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Get("Accept")
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	_, _ = c.Countries().List(context.Background())
	if got != "application/json" {
		t.Errorf("Accept: %q", got)
	}
}

func TestHeaders_ContentTypeOnlyForJSONBody(t *testing.T) {
	var post, get string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case "POST":
			post = r.Header.Get("Content-Type")
			_, _ = io.WriteString(w, `{}`)
		case "GET":
			get = r.Header.Get("Content-Type")
			_, _ = io.WriteString(w, `[]`)
		}
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	_, _ = c.Countries().List(context.Background())
	_, _ = c.Webhooks().Create(context.Background(), WebhookCreateOptions{
		URL: "https://e.x", EventTypes: []string{"law.updated"},
	})
	if post != "application/json" {
		t.Errorf("POST content-type: %q", post)
	}
	if get != "" {
		t.Errorf("GET should not send content-type: %q", get)
	}
}

func TestHeaders_ExtraHeadersPerRequest(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.Header.Get("X-Trace-Id")
		_, _ = io.WriteString(w, `[]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	h := http.Header{}
	h.Set("X-Trace-Id", "abc")
	_, _, err := c.Do(context.Background(), "GET", "/api/v1/countries", WithExtraHeaders(h))
	if err != nil {
		t.Fatal(err)
	}
	if got != "abc" {
		t.Errorf("got %q", got)
	}
}
