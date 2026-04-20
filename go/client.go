package legalize

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/legalize-dev/legalize-sdks/go/internal/useragent"
)

// API is the base path every resource prefixes onto its routes.
const API = "/api/v1"

// Client is the thread-safe entry point to the Legalize API.
//
// Construct with New and functional options. The zero value is NOT
// usable — always go through New so environment and defaults
// resolve correctly.
type Client struct {
	baseURL    string
	apiKey     string
	apiVersion string

	httpClient     *http.Client
	retry          RetryPolicy
	defaultHeaders http.Header
	userAgent      string

	// Resource services. Bound once per client at construction.
	countries     *CountriesService
	jurisdictions *JurisdictionsService
	lawTypes      *LawTypesService
	laws          *LawsService
	reforms       *ReformsService
	stats         *StatsService
	webhooks      *WebhooksService

	mu           sync.RWMutex
	lastResponse *http.Response
}

// New builds a Client from the given options. Missing values are
// resolved from the environment (LEGALIZE_API_KEY, LEGALIZE_BASE_URL,
// LEGALIZE_API_VERSION) and finally from the compiled-in defaults.
//
// Returns an *AuthenticationError when no API key can be resolved.
func New(opts ...Option) (*Client, error) {
	cfg := config{timeout: DefaultTimeout}
	for _, opt := range opts {
		opt(&cfg)
	}

	apiKey, err := resolveAPIKey(cfg.apiKey)
	if err != nil {
		return nil, err
	}

	httpClient := cfg.httpClient
	if httpClient == nil {
		httpClient = &http.Client{
			Timeout: cfg.timeout,
			// Never follow redirects — the server doesn't use them
			// and silent 301s would mask misconfigurations.
			CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
				return http.ErrUseLastResponse
			},
		}
	} else if cfg.timeout > 0 && httpClient.Timeout == 0 {
		// Respect the user's http.Client fully when they passed one,
		// but set the timeout if they did not.
		httpClient.Timeout = cfg.timeout
	}

	retry := resolveRetry(cfg.retry, cfg.maxRetries)

	c := &Client{
		baseURL:        resolveBaseURL(cfg.baseURL),
		apiKey:         apiKey,
		apiVersion:     resolveAPIVersion(cfg.apiVersion),
		httpClient:     httpClient,
		retry:          retry,
		defaultHeaders: cfg.defaultHeaders,
		userAgent:      useragent.Build(Version),
	}

	// Bind resource services.
	c.countries = &CountriesService{client: c}
	c.jurisdictions = &JurisdictionsService{client: c}
	c.lawTypes = &LawTypesService{client: c}
	c.laws = &LawsService{client: c}
	c.reforms = &ReformsService{client: c}
	c.stats = &StatsService{client: c}
	c.webhooks = &WebhooksService{client: c}

	return c, nil
}

func resolveRetry(policy *RetryPolicy, maxRetries *int) RetryPolicy {
	if policy != nil {
		return policy.withDefaults()
	}
	p := NewRetryPolicy()
	if maxRetries != nil {
		p.MaxRetries = *maxRetries
	}
	return p
}

// Close is a no-op that exists for API symmetry and defer-style use.
// The underlying *http.Client has no Close method; idle connections
// are released when it is garbage collected.
func (c *Client) Close() error { return nil }

// BaseURL returns the resolved API base URL.
func (c *Client) BaseURL() string { return c.baseURL }

// APIKey returns the resolved API key. Intentionally exported for
// debugging / logging scenarios; callers should scrub before logging.
func (c *Client) APIKey() string { return c.apiKey }

// APIVersion returns the resolved API version.
func (c *Client) APIVersion() string { return c.apiVersion }

// UserAgent returns the User-Agent header value the client sends.
func (c *Client) UserAgent() string { return c.userAgent }

// LastResponse returns the HTTP response from the most recent
// request, populated on both success and failure. Returns nil before
// any request has been issued. Concurrent calls are safe.
func (c *Client) LastResponse() *http.Response {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.lastResponse
}

// Countries returns the countries resource service.
func (c *Client) Countries() *CountriesService { return c.countries }

// Jurisdictions returns the jurisdictions resource service.
func (c *Client) Jurisdictions() *JurisdictionsService { return c.jurisdictions }

// LawTypes returns the law types resource service.
func (c *Client) LawTypes() *LawTypesService { return c.lawTypes }

// Laws returns the laws resource service.
func (c *Client) Laws() *LawsService { return c.laws }

// Reforms returns the reforms resource service.
func (c *Client) Reforms() *ReformsService { return c.reforms }

// Stats returns the stats resource service.
func (c *Client) Stats() *StatsService { return c.stats }

// Webhooks returns the webhooks management resource service.
func (c *Client) Webhooks() *WebhooksService { return c.webhooks }

// RequestOption configures a single Client.Do call.
type RequestOption func(*requestConfig)

type requestConfig struct {
	params       map[string]any
	body         any
	extraHeaders http.Header
}

// WithParams attaches query parameters to the request. Values are
// normalised per the SDK's contract: nil dropped, bool to "true"/"false",
// []string comma-joined, etc.
func WithParams(params map[string]any) RequestOption {
	return func(c *requestConfig) { c.params = params }
}

// WithJSONBody attaches a JSON body to the request.
func WithJSONBody(body any) RequestOption {
	return func(c *requestConfig) { c.body = body }
}

// WithExtraHeaders layers extra headers on top of the defaults for a
// single request.
func WithExtraHeaders(h http.Header) RequestOption {
	return func(c *requestConfig) { c.extraHeaders = h }
}

// Do executes a raw request. It is the escape hatch resources go
// through, and is exposed so callers can call endpoints the SDK has
// not yet wrapped. The returned *http.Response has its body already
// drained into the returned []byte; the response still carries
// headers + status for inspection.
func (c *Client) Do(ctx context.Context, method, path string, opts ...RequestOption) (*http.Response, []byte, error) {
	cfg := requestConfig{}
	for _, opt := range opts {
		opt(&cfg)
	}

	url, err := c.buildURL(path, cfg.params)
	if err != nil {
		return nil, nil, err
	}

	var bodyBytes []byte
	if cfg.body != nil {
		bodyBytes, err = json.Marshal(cfg.body)
		if err != nil {
			return nil, nil, fmt.Errorf("legalize: marshal body: %w", err)
		}
	}

	resp, data, err := c.sendWithRetry(ctx, method, url, bodyBytes, cfg.extraHeaders)
	if resp != nil {
		c.mu.Lock()
		c.lastResponse = resp
		c.mu.Unlock()
	}
	return resp, data, err
}

// buildURL assembles the full URL for a request path and optional
// params.
func (c *Client) buildURL(path string, params map[string]any) (string, error) {
	var full string
	if strings.HasPrefix(path, "http://") || strings.HasPrefix(path, "https://") {
		full = path
	} else {
		if !strings.HasPrefix(path, "/") {
			path = "/" + path
		}
		full = c.baseURL + path
	}
	if len(params) == 0 {
		return full, nil
	}
	u, err := url.Parse(full)
	if err != nil {
		return "", fmt.Errorf("legalize: parse url %q: %w", full, err)
	}
	q := u.Query()
	for k, v := range cleanParams(params) {
		q.Set(k, v)
	}
	u.RawQuery = q.Encode()
	return u.String(), nil
}

// cleanParams mirrors Python's _clean_params: drop nils/empty slices,
// coerce bools to "true"/"false", comma-join []string.
func cleanParams(params map[string]any) map[string]string {
	out := map[string]string{}
	for k, v := range params {
		if v == nil {
			continue
		}
		switch vv := v.(type) {
		case *string:
			if vv == nil || *vv == "" {
				continue
			}
			out[k] = *vv
		case *int:
			if vv == nil {
				continue
			}
			out[k] = strconv.Itoa(*vv)
		case *bool:
			if vv == nil {
				continue
			}
			if *vv {
				out[k] = "true"
			} else {
				out[k] = "false"
			}
		case string:
			if vv == "" {
				continue
			}
			out[k] = vv
		case int:
			out[k] = strconv.Itoa(vv)
		case int64:
			out[k] = strconv.FormatInt(vv, 10)
		case bool:
			if vv {
				out[k] = "true"
			} else {
				out[k] = "false"
			}
		case float64:
			out[k] = strconv.FormatFloat(vv, 'f', -1, 64)
		case []string:
			if len(vv) == 0 {
				continue
			}
			out[k] = strings.Join(vv, ",")
		case []any:
			if len(vv) == 0 {
				continue
			}
			parts := make([]string, 0, len(vv))
			for _, x := range vv {
				parts = append(parts, fmt.Sprintf("%v", x))
			}
			out[k] = strings.Join(parts, ",")
		default:
			out[k] = fmt.Sprintf("%v", vv)
		}
	}
	return out
}

// sendWithRetry runs the request with the retry policy applied.
func (c *Client) sendWithRetry(ctx context.Context, method, url string, body []byte, extraHeaders http.Header) (*http.Response, []byte, error) {
	method = strings.ToUpper(method)
	_, idempotent := idempotentMethods[method]
	attempt := 0

	for {
		req, err := c.buildRequest(ctx, method, url, body, extraHeaders)
		if err != nil {
			return nil, nil, err
		}

		resp, err := c.httpClient.Do(req)
		if err != nil {
			// Transport failure: retry only for idempotent methods,
			// and only while the policy allows it.
			if idempotent && c.retry.ShouldRetry(attempt, -1) {
				delay := c.retry.ComputeDelay(attempt, nil)
				if !sleepOrCancel(ctx, delay) {
					return nil, nil, mapTransportErr(ctx.Err())
				}
				attempt++
				continue
			}
			return nil, nil, mapTransportErr(err)
		}

		data, readErr := io.ReadAll(resp.Body)
		_ = resp.Body.Close()
		if readErr != nil {
			return resp, nil, &APIConnectionError{Cause: readErr}
		}

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return resp, data, nil
		}

		// Non-2xx. Decide whether to retry.
		if idempotent && c.retry.ShouldRetry(attempt, resp.StatusCode) {
			retryAfter := parseRetryAfter(resp.Header.Get("Retry-After"))
			delay := c.retry.ComputeDelay(attempt, retryAfter)
			if !sleepOrCancel(ctx, delay) {
				return resp, data, mapTransportErr(ctx.Err())
			}
			attempt++
			continue
		}
		// Final response — surface as typed error.
		return resp, data, ErrorFromResponse(resp, data)
	}
}

// buildRequest assembles an *http.Request with all SDK-required
// headers applied.
func (c *Client) buildRequest(ctx context.Context, method, url string, body []byte, extraHeaders http.Header) (*http.Request, error) {
	var reader io.Reader
	if len(body) > 0 {
		reader = bytes.NewReader(body)
	}
	req, err := http.NewRequestWithContext(ctx, method, url, reader)
	if err != nil {
		return nil, fmt.Errorf("legalize: build request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("User-Agent", c.userAgent)
	req.Header.Set("Legalize-API-Version", c.apiVersion)
	req.Header.Set("Accept", "application/json")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	for k, vs := range c.defaultHeaders {
		for _, v := range vs {
			req.Header.Set(k, v)
		}
	}
	for k, vs := range extraHeaders {
		for _, v := range vs {
			req.Header.Set(k, v)
		}
	}
	return req, nil
}

// sleepOrCancel sleeps for d, returning false if the context is
// cancelled first.
func sleepOrCancel(ctx context.Context, d time.Duration) bool {
	if d <= 0 {
		select {
		case <-ctx.Done():
			return false
		default:
			return true
		}
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-t.C:
		return true
	}
}

// mapTransportErr converts a transport-layer error into the typed
// APIConnectionError / APITimeoutError.
func mapTransportErr(err error) error {
	if err == nil {
		return nil
	}
	if errors.Is(err, context.DeadlineExceeded) {
		return &APITimeoutError{Cause: err}
	}
	var netErr interface{ Timeout() bool }
	if errors.As(err, &netErr) && netErr.Timeout() {
		return &APITimeoutError{Cause: err}
	}
	return &APIConnectionError{Cause: err}
}

// requestJSON is the internal helper every resource uses. It performs
// a request and unmarshals a 2xx JSON body into dst. Pass dst=nil to
// skip the unmarshal (e.g. delete calls returning {}).
func (c *Client) requestJSON(ctx context.Context, method, path string, opts []RequestOption, dst any) error {
	resp, data, err := c.Do(ctx, method, path, opts...)
	_ = resp
	if err != nil {
		return err
	}
	if dst == nil || len(data) == 0 {
		return nil
	}
	if err := json.Unmarshal(data, dst); err != nil {
		return &APIError{
			StatusCode: resp.StatusCode,
			Message:    "server returned non-JSON body",
			Body:       data,
			Response:   resp,
		}
	}
	return nil
}
