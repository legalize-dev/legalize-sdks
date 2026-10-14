package legalize

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
)

func TestHistoricalMetadataSurvivesResources(t *testing.T) {
	for _, state := range []string{"current", "as_enacted", "point_in_time", "future_state"} {
		for _, method := range []string{"date", "commit"} {
			t.Run(state+"/"+method, func(t *testing.T) {
				kind := state
				if state == "point_in_time" {
					kind = "consolidated"
				}
				basis := "recorded_on_or_before"
				var superseded any = state == "as_enacted"
				if state == "current" {
					superseded = nil
					basis = "current_snapshot"
				}
				metadata := map[string]any{
					"kind": kind, "text_state": state, "status": "partially_repealed",
					"in_force": nil, "source_url": "https://example.test/official-version",
					"basis": basis, "text_superseded": superseded,
					"warning":      "This snapshot does not establish historical wording.",
					"amended_by":   []any{map[string]any{"source_id": "IE-2021-act-4"}},
					"source_notes": []any{map[string]any{"type": nil, "text": "Source's note"}},
				}
				payload := map[string]any{
					"law_id": "IE-1995-act-2", "sha": "abcdef1", "content_md": "Complete law text.",
					"date": "2023-07-03", "version_date": "2023-07-03",
					"citation": "Source snapshot", "citation_url": "https://example.test/citation",
				}
				for key, value := range metadata {
					payload[key] = value
				}
				srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
					if err := json.NewEncoder(w).Encode(payload); err != nil {
						t.Error(err)
					}
				}))
				defer srv.Close()
				client, err := New(WithAPIKey("leg_test"), WithBaseURL(srv.URL), WithMaxRetries(0))
				if err != nil {
					t.Fatal(err)
				}
				var result any
				if method == "date" {
					result, err = client.Laws().AtDate(context.Background(), "ie", "IE-1995-act-2", "2023-07-03")
				} else {
					result, err = client.Laws().AtCommit(context.Background(), "ie", "IE-1995-act-2", "abcdef1")
				}
				if err != nil {
					t.Fatal(err)
				}
				encoded, err := json.Marshal(result)
				if err != nil {
					t.Fatal(err)
				}
				var decoded map[string]any
				if err := json.Unmarshal(encoded, &decoded); err != nil {
					t.Fatal(err)
				}
				for key, expected := range metadata {
					actual, found := decoded[key]
					if !found || !reflect.DeepEqual(actual, expected) {
						t.Errorf("%s: got %#v, want %#v", key, actual, expected)
					}
				}
			})
		}
	}
}

func TestLatestSourceWarningSurvivesResource(t *testing.T) {
	warning := "The source omits a provision; consult the amending Act."
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		if err := json.NewEncoder(w).Encode(map[string]any{
			"id": "IE-2014-act-38", "title": "Companies Act 2014", "country": "ie",
			"law_type": "act", "kind": "incomplete", "text_state": "point_in_time", "warning": warning,
		}); err != nil {
			t.Error(err)
		}
	}))
	defer srv.Close()
	client, err := New(WithAPIKey("leg_test"), WithBaseURL(srv.URL), WithMaxRetries(0))
	if err != nil {
		t.Fatal(err)
	}
	got, err := client.Laws().Retrieve(context.Background(), "ie", "IE-2014-act-38")
	if err != nil {
		t.Fatal(err)
	}
	if got.Kind != "incomplete" || got.TextState != "point_in_time" || got.Warning == nil || *got.Warning != warning {
		t.Fatalf("Source warning lost: %#v", got)
	}
}
