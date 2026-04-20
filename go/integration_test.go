//go:build integration

// Read-only integration tests against the live Legalize API.
//
// Run with:
//
//	LEGALIZE_API_KEY=leg_... go test -tags=integration -v ./...
//
// Skipped by default so `go test ./...` stays offline. CI runs these
// daily via .github/workflows/go-integration.yml.
//
// Assertions target contract shape, not row counts that drift over
// time.

package legalize_test

import (
	"context"
	"errors"
	"os"
	"testing"

	legalize "github.com/legalize-dev/legalize-sdks/go"
)

func newLiveClient(t *testing.T) *legalize.Client {
	t.Helper()
	key := os.Getenv("LEGALIZE_API_KEY")
	if key == "" {
		t.Skip("LEGALIZE_API_KEY not set")
	}
	baseURL := os.Getenv("LEGALIZE_BASE_URL")
	if baseURL == "" {
		baseURL = "https://legalize.dev"
	}
	client, err := legalize.New(
		legalize.WithAPIKey(key),
		legalize.WithBaseURL(baseURL),
	)
	if err != nil {
		t.Fatalf("new client: %v", err)
	}
	t.Cleanup(func() { _ = client.Close() })
	return client
}

func TestIntegrationCountries(t *testing.T) {
	client := newLiveClient(t)
	ctx := context.Background()

	countries, err := client.Countries().List(ctx)
	if err != nil {
		t.Fatalf("countries.list: %v", err)
	}
	if len(countries) == 0 {
		t.Fatal("expected at least one country")
	}
	var found bool
	for _, c := range countries {
		if c.Country == "es" {
			found = true
			break
		}
	}
	if !found {
		t.Error("expected 'es' in countries")
	}
}

func TestIntegrationJurisdictionsUnknown404(t *testing.T) {
	client := newLiveClient(t)
	_, err := client.Jurisdictions().List(context.Background(), "zz")
	var nf *legalize.NotFoundError
	if !errors.As(err, &nf) {
		t.Fatalf("expected NotFoundError, got %v", err)
	}
}

func TestIntegrationLawsList(t *testing.T) {
	client := newLiveClient(t)
	page, err := client.Laws().List(context.Background(), "es", &legalize.LawsListOptions{
		Page:    legalize.Int(1),
		PerPage: legalize.Int(5),
	})
	if err != nil {
		t.Fatalf("laws.list: %v", err)
	}
	if page.Country != "es" {
		t.Errorf("country = %q, want es", page.Country)
	}
	if page.Total <= 0 {
		t.Error("expected positive total")
	}
	if len(page.Results) > 5 {
		t.Errorf("per_page not honored: got %d results", len(page.Results))
	}
}

func TestIntegrationLawsSearch(t *testing.T) {
	client := newLiveClient(t)
	page, err := client.Laws().Search(context.Background(), "es", "protección de datos", &legalize.LawsListOptions{
		PerPage: legalize.Int(3),
	})
	if err != nil {
		t.Fatalf("laws.search: %v", err)
	}
	if page.Total <= 0 {
		t.Error("expected matches for common query")
	}
}

func TestIntegrationLawsRetrieve404(t *testing.T) {
	client := newLiveClient(t)
	_, err := client.Laws().Retrieve(context.Background(), "es", "does_not_exist_xxxxx")
	var nf *legalize.NotFoundError
	if !errors.As(err, &nf) {
		t.Fatalf("expected NotFoundError, got %v", err)
	}
}

func TestIntegrationStats(t *testing.T) {
	client := newLiveClient(t)
	stats, err := client.Stats().Retrieve(context.Background(), "es", nil)
	if err != nil {
		t.Fatalf("stats.retrieve: %v", err)
	}
	if stats.Country != "es" {
		t.Errorf("country = %q, want es", stats.Country)
	}
}
