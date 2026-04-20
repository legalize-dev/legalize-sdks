package legalize

import (
	"net/http"
	"time"
)

// DefaultTimeout is the total per-request timeout when none is set.
const DefaultTimeout = 30 * time.Second

// Option configures a Client. Options apply at construction time.
type Option func(*config)

// config is the internal construction bag. Pointer-typed fields
// capture "explicit vs unset" for the env-backed settings so the
// resolver helpers can honour the precedence contract.
type config struct {
	apiKey     *string
	baseURL    *string
	apiVersion *string

	timeout        time.Duration
	maxRetries     *int
	retry          *RetryPolicy
	httpClient     *http.Client
	defaultHeaders http.Header
}

// WithAPIKey sets the Legalize API key explicitly. An explicit value
// always wins over LEGALIZE_API_KEY.
func WithAPIKey(key string) Option {
	return func(c *config) { c.apiKey = &key }
}

// WithBaseURL overrides the API base URL. Explicit value wins over
// LEGALIZE_BASE_URL.
func WithBaseURL(baseURL string) Option {
	return func(c *config) { c.baseURL = &baseURL }
}

// WithAPIVersion sets the Legalize-API-Version header value. Explicit
// value wins over LEGALIZE_API_VERSION.
func WithAPIVersion(v string) Option {
	return func(c *config) { c.apiVersion = &v }
}

// WithTimeout sets the total per-request timeout. A zero duration
// disables the timeout.
func WithTimeout(d time.Duration) Option {
	return func(c *config) { c.timeout = d }
}

// WithMaxRetries sets only the retry count. Use WithRetryPolicy when
// the full policy needs customising.
func WithMaxRetries(n int) Option {
	return func(c *config) { c.maxRetries = &n }
}

// WithRetryPolicy sets the full retry policy. Overrides WithMaxRetries.
func WithRetryPolicy(p RetryPolicy) Option {
	return func(c *config) { c.retry = &p }
}

// WithHTTPClient swaps the underlying *http.Client. Useful for tests
// that plug in an httptest.Server's Client(), for custom transports,
// or for connection-pool tuning.
func WithHTTPClient(client *http.Client) Option {
	return func(c *config) { c.httpClient = client }
}

// WithDefaultHeaders merges additional headers into every outgoing
// request. Keys collide-check: Authorization, User-Agent and
// Legalize-API-Version are always set by the SDK and can't be
// overridden through this option.
func WithDefaultHeaders(h http.Header) Option {
	return func(c *config) {
		if c.defaultHeaders == nil {
			c.defaultHeaders = http.Header{}
		}
		for k, vs := range h {
			for _, v := range vs {
				c.defaultHeaders.Add(k, v)
			}
		}
	}
}
