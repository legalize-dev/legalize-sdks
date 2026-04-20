package legalize

import (
	"errors"
	"strings"
	"testing"
)

// Mirrors python/tests/unit/test_env_resolution.py — the cross-SDK
// env-var contract. Every case there should have a case here.

func clearEnv(t *testing.T) {
	t.Helper()
	t.Setenv("LEGALIZE_API_KEY", "")
	t.Setenv("LEGALIZE_BASE_URL", "")
	t.Setenv("LEGALIZE_API_VERSION", "")
	// Setenv sets to empty; we want it truly unset. Go's testing
	// Setenv doesn't support unset, so we rely on env.go treating ""
	// as unset — which is the documented contract.
}

// ---- LEGALIZE_API_KEY --------------------------------------------------

func TestApiKey_MissingRaises(t *testing.T) {
	clearEnv(t)
	_, err := New()
	if err == nil {
		t.Fatal("expected error when no API key")
	}
	var ae *AuthenticationError
	if !errors.As(err, &ae) {
		t.Fatalf("expected AuthenticationError, got %T: %v", err, err)
	}
	if ae.Code != "missing_api_key" {
		t.Errorf("got code %q, want %q", ae.Code, "missing_api_key")
	}
}

func TestApiKey_EmptyStringTreatedAsMissing(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "")
	_, err := New()
	var ae *AuthenticationError
	if !errors.As(err, &ae) || ae.Code != "missing_api_key" {
		t.Fatalf("want missing_api_key, got %v", err)
	}
}

func TestApiKey_EnvProvidesKey(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_env_abc")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if c.APIKey() != "leg_env_abc" {
		t.Errorf("got %q", c.APIKey())
	}
}

func TestApiKey_ExplicitWinsOverEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_env_abc")
	c, err := New(WithAPIKey("leg_arg_xyz"))
	if err != nil {
		t.Fatal(err)
	}
	if c.APIKey() != "leg_arg_xyz" {
		t.Errorf("got %q", c.APIKey())
	}
}

func TestApiKey_InvalidPrefixRejectedEarly(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "sk_wrong")
	_, err := New()
	var ae *AuthenticationError
	if !errors.As(err, &ae) || ae.Code != "invalid_api_key" {
		t.Fatalf("want invalid_api_key, got %v", err)
	}
}

// ---- LEGALIZE_BASE_URL -------------------------------------------------

func TestBaseURL_ResolverDefault(t *testing.T) {
	clearEnv(t)
	got := resolveBaseURL(nil)
	if got != DefaultBaseURL {
		t.Errorf("got %q want %q", got, DefaultBaseURL)
	}
}

func TestBaseURL_ResolverUsesEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
	if got := resolveBaseURL(nil); got != "https://staging.legalize.dev" {
		t.Errorf("got %q", got)
	}
}

func TestBaseURL_ResolverExplicitWins(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
	explicit := "https://other.example"
	if got := resolveBaseURL(&explicit); got != "https://other.example" {
		t.Errorf("got %q", got)
	}
}

func TestBaseURL_ResolverEmptyFallsThrough(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_BASE_URL", "")
	if got := resolveBaseURL(nil); got != DefaultBaseURL {
		t.Errorf("got %q", got)
	}
}

func TestBaseURL_ClientHonorsEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_t")
	t.Setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if c.BaseURL() != "https://staging.legalize.dev" {
		t.Errorf("got %q", c.BaseURL())
	}
}

func TestBaseURL_StripsTrailingSlash(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_t")
	t.Setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev/")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if c.BaseURL() != "https://staging.legalize.dev" {
		t.Errorf("got %q", c.BaseURL())
	}
}

func TestBaseURL_ExplicitArgWinsOverEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_t")
	t.Setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
	c, err := New(WithBaseURL("https://explicit.example"))
	if err != nil {
		t.Fatal(err)
	}
	if c.BaseURL() != "https://explicit.example" {
		t.Errorf("got %q", c.BaseURL())
	}
}

// ---- LEGALIZE_API_VERSION ---------------------------------------------

func TestAPIVersion_ResolverDefault(t *testing.T) {
	clearEnv(t)
	if got := resolveAPIVersion(nil); got != DefaultAPIVersion {
		t.Errorf("got %q", got)
	}
}

func TestAPIVersion_ResolverUsesEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_VERSION", "v2")
	if got := resolveAPIVersion(nil); got != "v2" {
		t.Errorf("got %q", got)
	}
}

func TestAPIVersion_ResolverExplicitWins(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_VERSION", "v2")
	v := "v99"
	if got := resolveAPIVersion(&v); got != "v99" {
		t.Errorf("got %q", got)
	}
}

func TestAPIVersion_ResolverEmptyFallsThrough(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_VERSION", "")
	if got := resolveAPIVersion(nil); got != DefaultAPIVersion {
		t.Errorf("got %q", got)
	}
}

func TestAPIVersion_ClientHonorsEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_t")
	t.Setenv("LEGALIZE_API_VERSION", "v42")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if c.APIVersion() != "v42" {
		t.Errorf("got %q", c.APIVersion())
	}
}

func TestAPIVersion_ExplicitWinsOverEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_t")
	t.Setenv("LEGALIZE_API_VERSION", "v42")
	c, err := New(WithAPIVersion("v1"))
	if err != nil {
		t.Fatal(err)
	}
	if c.APIVersion() != "v1" {
		t.Errorf("got %q", c.APIVersion())
	}
}

// ---- Zero-config construction -----------------------------------------

func TestZeroConfig_FullEnv(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_prod_xyz")
	t.Setenv("LEGALIZE_BASE_URL", "https://api.internal.example")
	t.Setenv("LEGALIZE_API_VERSION", "v1")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if c.APIKey() != "leg_prod_xyz" {
		t.Error("api key")
	}
	if c.BaseURL() != "https://api.internal.example" {
		t.Error("base url")
	}
	if c.APIVersion() != "v1" {
		t.Error("api version")
	}
	ua := c.UserAgent()
	if !strings.HasPrefix(ua, "legalize-go/"+Version+" ") {
		t.Errorf("user-agent: %q", ua)
	}
}

func TestZeroConfig_OnlyAPIKey(t *testing.T) {
	clearEnv(t)
	t.Setenv("LEGALIZE_API_KEY", "leg_prod_xyz")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if c.BaseURL() != DefaultBaseURL {
		t.Error("base url default")
	}
	if c.APIVersion() != DefaultAPIVersion {
		t.Error("api version default")
	}
}
