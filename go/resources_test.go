package legalize

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// Each resource test spins a dedicated httptest.Server, asserts on the
// incoming request (method, path, query, body, headers), and returns a
// canned response. The goal is to prove that every SDK method hits the
// correct URL with the correct params and parses the expected shape.

func assertMethodPath(t *testing.T, r *http.Request, method, path string) {
	t.Helper()
	if r.Method != method {
		t.Errorf("method: got %s, want %s", r.Method, method)
	}
	if r.URL.Path != path {
		t.Errorf("path: got %s, want %s", r.URL.Path, path)
	}
}

// ---- countries --------------------------------------------------------

func TestCountries_List(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/countries")
		_, _ = io.WriteString(w, `[{"country":"es","count":1234}]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	list, err := c.Countries().List(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 1 || list[0].Country != "es" || list[0].Count != 1234 {
		t.Errorf("got %+v", list)
	}
}

// ---- jurisdictions ----------------------------------------------------

func TestJurisdictions_List(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/jurisdictions")
		_, _ = io.WriteString(w, `[{"jurisdiction":"cat","count":100},{"jurisdiction":null,"count":50}]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	list, err := c.Jurisdictions().List(context.Background(), "es")
	if err != nil {
		t.Fatal(err)
	}
	if len(list) != 2 {
		t.Fatalf("got %d", len(list))
	}
	if list[0].Jurisdiction == nil || *list[0].Jurisdiction != "cat" {
		t.Errorf("first: %+v", list[0])
	}
	if list[1].Jurisdiction != nil {
		t.Errorf("second should be nil: %+v", list[1])
	}
}

// ---- law types --------------------------------------------------------

func TestLawTypes_List(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/law-types")
		_, _ = io.WriteString(w, `["ley","real_decreto"]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	types, err := c.LawTypes().List(context.Background(), "es")
	if err != nil {
		t.Fatal(err)
	}
	if len(types) != 2 || types[0] != "ley" {
		t.Errorf("got %+v", types)
	}
}

// ---- laws.list --------------------------------------------------------

func TestLaws_List_SerialisesParams(t *testing.T) {
	var captured *http.Request
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = r.Clone(context.Background())
		resp := PaginatedLaws{Country: "es", Total: 0, Page: 1, PerPage: 20, Results: []LawSearchResult{}}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	_, err := c.Laws().List(context.Background(), "es", &LawsListOptions{
		Page:    Int(2),
		PerPage: Int(20),
		LawType: []string{"ley", "constitucion"},
		Year:    Int(2024),
		Status:  String("vigente"),
	})
	if err != nil {
		t.Fatal(err)
	}
	q := captured.URL.Query()
	if q.Get("page") != "2" {
		t.Errorf("page: %q", q.Get("page"))
	}
	if q.Get("per_page") != "20" {
		t.Errorf("per_page: %q", q.Get("per_page"))
	}
	if q.Get("law_type") != "ley,constitucion" {
		t.Errorf("law_type: %q", q.Get("law_type"))
	}
	if q.Get("year") != "2024" {
		t.Errorf("year: %q", q.Get("year"))
	}
	if q.Get("status") != "vigente" {
		t.Errorf("status: %q", q.Get("status"))
	}
	// nil fields MUST NOT be serialised.
	if q.Has("sort") || q.Has("from_date") {
		t.Errorf("nil fields should not be sent: %v", q)
	}
}

func TestLaws_List_NoOptions(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/laws")
		if len(r.URL.Query()) != 0 {
			t.Errorf("expected no query: %v", r.URL.Query())
		}
		resp := PaginatedLaws{Country: "es", Total: 0, Page: 1, PerPage: 50, Results: []LawSearchResult{}}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Laws().List(context.Background(), "es", nil); err != nil {
		t.Fatal(err)
	}
}

// ---- laws.search ------------------------------------------------------

func TestLaws_Search_RequiresQuery(t *testing.T) {
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL("http://x"), WithMaxRetries(0))
	_, err := c.Laws().Search(context.Background(), "es", "", nil)
	if err == nil {
		t.Fatal("expected error for empty query")
	}
}

func TestLaws_Search_PassesQ(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r.URL.Query().Get("q")
		resp := PaginatedLaws{Country: "es", Total: 0, Page: 1, PerPage: 50, Results: []LawSearchResult{}}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Laws().Search(context.Background(), "es", "elections", nil); err != nil {
		t.Fatal(err)
	}
	if got != "elections" {
		t.Errorf("q: %q", got)
	}
}

// ---- laws.retrieve / meta / commits / at_commit -----------------------

func TestLaws_Retrieve(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/laws/BOE-A-2025-001")
		_, _ = io.WriteString(w, `{"id":"BOE-A-2025-001","title":"T","country":"es","law_type":"ley","content_md":"# hi"}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	d, err := c.Laws().Retrieve(context.Background(), "es", "BOE-A-2025-001")
	if err != nil {
		t.Fatal(err)
	}
	if d.ContentMD == nil || *d.ContentMD != "# hi" {
		t.Errorf("md: %+v", d.ContentMD)
	}
}

func TestLaws_Meta(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/laws/BOE-A-2025-001/meta")
		_, _ = io.WriteString(w, `{"id":"BOE-A-2025-001","title":"T","country":"es","law_type":"ley"}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	m, err := c.Laws().Meta(context.Background(), "es", "BOE-A-2025-001")
	if err != nil {
		t.Fatal(err)
	}
	if m.Title != "T" {
		t.Errorf("title: %q", m.Title)
	}
}

func TestLaws_Commits(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/laws/L/commits")
		_, _ = io.WriteString(w, `{"law_id":"L","commits":[{"sha":"abc","date":"2024","message":"m"}]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	r, err := c.Laws().Commits(context.Background(), "es", "L")
	if err != nil {
		t.Fatal(err)
	}
	if len(r.Commits) != 1 || r.Commits[0].SHA != "abc" {
		t.Errorf("got %+v", r)
	}
}

func TestLaws_AtCommit(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/laws/L/at/deadbeef")
		_, _ = io.WriteString(w, `{"law_id":"L","sha":"deadbeef","content_md":"# old"}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	r, err := c.Laws().AtCommit(context.Background(), "es", "L", "deadbeef")
	if err != nil {
		t.Fatal(err)
	}
	if r.SHA != "deadbeef" {
		t.Errorf("sha: %q", r.SHA)
	}
}

// ---- reforms ----------------------------------------------------------

func TestReforms_List(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/laws/L/reforms")
		if r.URL.Query().Get("limit") != "10" {
			t.Errorf("limit: %q", r.URL.Query().Get("limit"))
		}
		_, _ = io.WriteString(w, `{"law_id":"L","total":2,"offset":0,"limit":10,"reforms":[{"date":"2020-01-01"}]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	r, err := c.Reforms().List(context.Background(), "es", "L", &ReformsListOptions{Limit: Int(10)})
	if err != nil {
		t.Fatal(err)
	}
	if r.Total != 2 {
		t.Errorf("total: %d", r.Total)
	}
}

// ---- stats ------------------------------------------------------------

func TestStats_Retrieve_WithJurisdiction(t *testing.T) {
	var got string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/es/stats")
		got = r.URL.Query().Get("jurisdiction")
		_, _ = io.WriteString(w, `{"country":"es","law_types":[],"most_reformed_laws":[],"reform_activity_by_year":[]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Stats().Retrieve(context.Background(), "es", &StatsOptions{Jurisdiction: String("cat")}); err != nil {
		t.Fatal(err)
	}
	if got != "cat" {
		t.Errorf("jurisdiction: %q", got)
	}
}

func TestStats_Retrieve_NoOptions(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("jurisdiction") != "" {
			t.Errorf("unexpected jurisdiction: %q", r.URL.Query().Get("jurisdiction"))
		}
		_, _ = io.WriteString(w, `{"country":"es","law_types":[],"most_reformed_laws":[],"reform_activity_by_year":[]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Stats().Retrieve(context.Background(), "es", nil); err != nil {
		t.Fatal(err)
	}
}

// ---- webhooks (resource, not signature verify) ------------------------

func TestWebhooks_Create(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "POST", "/api/v1/webhooks")
		var body WebhookEndpointCreate
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body.URL != "https://example.com/hook" {
			t.Errorf("url: %q", body.URL)
		}
		if len(body.EventTypes) != 1 || body.EventTypes[0] != "law.updated" {
			t.Errorf("events: %+v", body.EventTypes)
		}
		_, _ = io.WriteString(w, `{"id":1,"secret":"whsec_abc","url":"https://example.com/hook"}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	out, err := c.Webhooks().Create(context.Background(), WebhookCreateOptions{
		URL:        "https://example.com/hook",
		EventTypes: []string{"law.updated"},
	})
	if err != nil {
		t.Fatal(err)
	}
	if out["secret"] != "whsec_abc" {
		t.Errorf("secret: %v", out["secret"])
	}
}

func TestWebhooks_List(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/webhooks")
		_, _ = io.WriteString(w, `[{"id":1},{"id":2}]`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	out, err := c.Webhooks().List(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(out) != 2 {
		t.Errorf("got %d", len(out))
	}
}

func TestWebhooks_Retrieve(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/webhooks/42")
		_, _ = io.WriteString(w, `{"id":42}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	out, err := c.Webhooks().Retrieve(context.Background(), 42)
	if err != nil {
		t.Fatal(err)
	}
	if out["id"].(float64) != 42 {
		t.Errorf("id: %+v", out["id"])
	}
}

func TestWebhooks_Update(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "PATCH", "/api/v1/webhooks/3")
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), `"url":"https://new"`) {
			t.Errorf("body: %s", body)
		}
		_, _ = io.WriteString(w, `{"id":3}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Webhooks().Update(context.Background(), 3, WebhookUpdateOptions{
		URL: String("https://new"),
	}); err != nil {
		t.Fatal(err)
	}
}

func TestWebhooks_Delete(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "DELETE", "/api/v1/webhooks/7")
		w.WriteHeader(204)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if err := c.Webhooks().Delete(context.Background(), 7); err != nil {
		t.Fatal(err)
	}
}

func TestWebhooks_Deliveries_ValidatesStatus(t *testing.T) {
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL("http://x"), WithMaxRetries(0))
	_, err := c.Webhooks().Deliveries(context.Background(), 1, &WebhookDeliveriesOptions{Status: String("bogus")})
	if err == nil {
		t.Fatal("expected error for invalid status")
	}
}

func TestWebhooks_Deliveries_OK(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "GET", "/api/v1/webhooks/1/deliveries")
		if r.URL.Query().Get("status") != "failed" {
			t.Errorf("status: %q", r.URL.Query().Get("status"))
		}
		_, _ = io.WriteString(w, `{"items":[]}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Webhooks().Deliveries(context.Background(), 1, &WebhookDeliveriesOptions{Status: String("failed"), Page: Int(2)}); err != nil {
		t.Fatal(err)
	}
}

func TestWebhooks_Retry(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "POST", "/api/v1/webhooks/1/deliveries/5/retry")
		_, _ = io.WriteString(w, `{"ok":true}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Webhooks().Retry(context.Background(), 1, 5); err != nil {
		t.Fatal(err)
	}
}

func TestWebhooks_Test(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertMethodPath(t, r, "POST", "/api/v1/webhooks/1/test")
		_, _ = io.WriteString(w, `{"sent":true}`)
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if _, err := c.Webhooks().Test(context.Background(), 1); err != nil {
		t.Fatal(err)
	}
}

// ---- iterator integration test (short path / total exhausted) ---------

func TestLawsIter_Integration(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		page, _ := parseIntSafe(r.URL.Query().Get("page"))
		if page == 0 {
			page = 1
		}
		// Two pages of 2 items each, then empty — total=3.
		var items []LawSearchResult
		total := 3
		switch page {
		case 1:
			items = []LawSearchResult{
				{ID: "a", Title: "t", Country: "es", LawType: "ley"},
				{ID: "b", Title: "t", Country: "es", LawType: "ley"},
			}
		case 2:
			items = []LawSearchResult{
				{ID: "c", Title: "t", Country: "es", LawType: "ley"},
			}
		default:
			items = nil
		}
		_ = json.NewEncoder(w).Encode(PaginatedLaws{Country: "es", Total: total, Page: page, PerPage: 2, Results: items})
	}))
	defer srv.Close()
	c, _ := New(WithAPIKey("leg_t"), WithBaseURL(srv.URL), WithMaxRetries(0))
	it := c.Laws().Iter(context.Background(), "es", 2, 0, nil)
	var ids []string
	for {
		item, ok, err := it.Next(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		if !ok {
			break
		}
		ids = append(ids, item.ID)
	}
	if strings.Join(ids, ",") != "a,b,c" {
		t.Errorf("ids: %v", ids)
	}
}

func parseIntSafe(s string) (int, error) {
	if s == "" {
		return 0, nil
	}
	var n int
	for _, r := range s {
		if r < '0' || r > '9' {
			return 0, nil
		}
		n = n*10 + int(r-'0')
	}
	return n, nil
}
