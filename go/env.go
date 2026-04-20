package legalize

import "os"

// Default values for the three env-backed settings. Match Python and
// Node byte-for-byte.
const (
	DefaultBaseURL    = "https://legalize.dev"
	DefaultAPIVersion = "v1"

	envAPIKey     = "LEGALIZE_API_KEY" //nolint:gosec // this is an env var name, not a credential
	envBaseURL    = "LEGALIZE_BASE_URL"
	envAPIVersion = "LEGALIZE_API_VERSION"

	keyPrefix = "leg_"
)

// resolveAPIKey returns the API key, validates its prefix and
// produces a typed AuthenticationError when anything is wrong.
//
// explicit is the value passed to WithAPIKey. When it is nil the
// environment variable is consulted. Empty strings (both explicit and
// env) are treated as unset, matching Python.
func resolveAPIKey(explicit *string) (string, error) {
	var key string
	switch {
	case explicit != nil:
		key = *explicit
	default:
		key = os.Getenv(envAPIKey)
	}
	if key == "" {
		return "", &AuthenticationError{APIError: &APIError{
			StatusCode: 401,
			Code:       "missing_api_key",
			Message:    "Missing API key. Pass WithAPIKey(...) or set LEGALIZE_API_KEY.",
		}}
	}
	if len(key) < len(keyPrefix) || key[:len(keyPrefix)] != keyPrefix {
		return "", &AuthenticationError{APIError: &APIError{
			StatusCode: 401,
			Code:       "invalid_api_key",
			Message:    "API key format unrecognized. Keys start with 'leg_'.",
		}}
	}
	return key, nil
}

// resolveBaseURL applies the explicit > env > default precedence.
// An empty string (explicit or env) is treated as unset.
func resolveBaseURL(explicit *string) string {
	if explicit != nil && *explicit != "" {
		return trimTrailingSlash(*explicit)
	}
	if v := os.Getenv(envBaseURL); v != "" {
		return trimTrailingSlash(v)
	}
	return DefaultBaseURL
}

// resolveAPIVersion applies the explicit > env > default precedence.
func resolveAPIVersion(explicit *string) string {
	if explicit != nil && *explicit != "" {
		return *explicit
	}
	if v := os.Getenv(envAPIVersion); v != "" {
		return v
	}
	return DefaultAPIVersion
}

func trimTrailingSlash(s string) string {
	for len(s) > 0 && s[len(s)-1] == '/' {
		s = s[:len(s)-1]
	}
	return s
}
