package legalize

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestContract_EveryOperationHasAMethod checks that every (method,
// path) pair declared in sdk/openapi-sdk.json has a corresponding
// SDK method. Failing this test means someone added a spec endpoint
// without adding the SDK wrapper.
func TestContract_EveryOperationHasAMethod(t *testing.T) {
	spec := loadSpec(t)

	paths, _ := spec["paths"].(map[string]any)
	if len(paths) == 0 {
		t.Fatal("openapi-sdk.json: paths empty")
	}

	// The SDK explicitly omits /api/health — it's a monitoring probe
	// that does not live behind the API key and thus has no client
	// method. PARITY.md §1 calls this out.
	excluded := map[string]bool{
		"GET /api/health": true,
	}

	// Expected mapping — update alongside PARITY.md §1.
	// Paths come straight from the spec; we normalise {param} braces
	// away because the SDK methods take params by name.
	expectedCovered := map[string]bool{
		// countries
		"GET /api/v1/countries": true,
		// jurisdictions
		"GET /api/v1/{country}/jurisdictions": true,
		// law types
		"GET /api/v1/{country}/law-types": true,
		// laws
		"GET /api/v1/{country}/laws":                   true,
		"GET /api/v1/{country}/laws/{law_id}":          true,
		"GET /api/v1/{country}/laws/{law_id}/meta":     true,
		"GET /api/v1/{country}/laws/{law_id}/commits":  true,
		"GET /api/v1/{country}/laws/{law_id}/at/{sha}": true,
		"GET /api/v1/{country}/laws/{law_id}/reforms":  true,
		// stats
		"GET /api/v1/{country}/stats": true,
		// webhooks
		"GET /api/v1/webhooks":                                               true,
		"POST /api/v1/webhooks":                                              true,
		"GET /api/v1/webhooks/{endpoint_id}":                                 true,
		"PATCH /api/v1/webhooks/{endpoint_id}":                               true,
		"DELETE /api/v1/webhooks/{endpoint_id}":                              true,
		"GET /api/v1/webhooks/{endpoint_id}/deliveries":                      true,
		"POST /api/v1/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry": true,
		"POST /api/v1/webhooks/{endpoint_id}/test":                           true,
	}

	for path, methods := range paths {
		ops, _ := methods.(map[string]any)
		for method := range ops {
			key := strings.ToUpper(method) + " " + path
			if excluded[key] {
				continue
			}
			if !expectedCovered[key] {
				t.Errorf("openapi-sdk.json declares %s but the SDK does not cover it", key)
			}
		}
	}
}

func loadSpec(t *testing.T) map[string]any {
	t.Helper()
	// Walk up from the test dir until we find the openapi-sdk.json.
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	candidates := []string{
		filepath.Join(wd, "..", "openapi-sdk.json"),
		filepath.Join(wd, "..", "..", "openapi-sdk.json"),
	}
	for _, path := range candidates {
		data, err := os.ReadFile(path) //nolint:gosec // test fixture
		if err != nil {
			continue
		}
		var out map[string]any
		if err := json.Unmarshal(data, &out); err != nil {
			t.Fatalf("parse %s: %v", path, err)
		}
		return out
	}
	t.Fatalf("openapi-sdk.json not found — tried %v", candidates)
	return nil
}
