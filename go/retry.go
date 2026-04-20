package legalize

import (
	"math"
	"math/rand"
	"net/http"
	"strconv"
	"strings"
	"time"
)

// Retry defaults. Match the Python SDK byte-for-byte.
const (
	DefaultMaxRetries    = 3
	DefaultInitialDelay  = 500 * time.Millisecond
	DefaultMaxDelay      = 30 * time.Second
	DefaultBackoffFactor = 2.0
)

// retryStatuses is the set of HTTP status codes that trigger a retry
// when returned by the server. Mirrors Python's RETRY_STATUSES.
var retryStatuses = map[int]struct{}{
	408: {},
	429: {},
	500: {},
	502: {},
	503: {},
	504: {},
}

// idempotentMethods is the set of HTTP methods that the SDK retries
// on transient failure by default. POST and PATCH are excluded to
// avoid duplicate webhook creation and duplicate retry-delivery
// calls. Callers can still opt into retrying those via the RequestOption
// mechanism.
var idempotentMethods = map[string]struct{}{
	http.MethodGet:     {},
	http.MethodHead:    {},
	http.MethodOptions: {},
	http.MethodPut:     {},
	http.MethodDelete:  {},
}

// RetryPolicy describes the SDK's transient-failure retry behaviour.
// Zero-value retries.MaxRetries disables retries entirely. Leave
// fields at their zero value to pick up the compiled-in defaults via
// the NewRetryPolicy helper.
type RetryPolicy struct {
	// MaxRetries caps the number of additional attempts after a
	// failure. Total requests is at most MaxRetries + 1.
	MaxRetries int
	// InitialDelay is the baseline backoff before the first retry.
	InitialDelay time.Duration
	// MaxDelay caps any single retry delay.
	MaxDelay time.Duration
	// BackoffFactor multiplies the delay each attempt (exponential).
	BackoffFactor float64
	// rng is an injectable jitter source for deterministic tests.
	// Left nil in the public API so users never see it.
	rng *rand.Rand
}

// NewRetryPolicy returns a RetryPolicy with the SDK defaults applied.
func NewRetryPolicy() RetryPolicy {
	return RetryPolicy{
		MaxRetries:    DefaultMaxRetries,
		InitialDelay:  DefaultInitialDelay,
		MaxDelay:      DefaultMaxDelay,
		BackoffFactor: DefaultBackoffFactor,
	}
}

// withDefaults fills any zero fields on the policy with the compiled-in
// defaults so callers can pass a partially-populated struct.
func (p RetryPolicy) withDefaults() RetryPolicy {
	if p.InitialDelay == 0 {
		p.InitialDelay = DefaultInitialDelay
	}
	if p.MaxDelay == 0 {
		p.MaxDelay = DefaultMaxDelay
	}
	if p.BackoffFactor == 0 {
		p.BackoffFactor = DefaultBackoffFactor
	}
	return p
}

// ShouldRetry decides whether the client should issue another attempt
// after the given 0-indexed failed attempt and HTTP status code.
// Pass status = -1 for a transport-layer failure (no response).
func (p RetryPolicy) ShouldRetry(attempt int, status int) bool {
	if attempt >= p.MaxRetries {
		return false
	}
	if status < 0 {
		return true
	}
	_, ok := retryStatuses[status]
	return ok
}

// ComputeDelay returns the sleep duration before the given retry.
// The server-provided Retry-After header wins unambiguously when
// present; otherwise we apply exponential backoff with full jitter,
// capped at MaxDelay.
func (p RetryPolicy) ComputeDelay(attempt int, retryAfter *time.Duration) time.Duration {
	p = p.withDefaults()
	if retryAfter != nil && *retryAfter >= 0 {
		if *retryAfter > p.MaxDelay {
			return p.MaxDelay
		}
		return *retryAfter
	}
	base := float64(p.InitialDelay) * math.Pow(p.BackoffFactor, float64(attempt))
	cap := float64(p.MaxDelay)
	if base > cap {
		base = cap
	}
	// Full jitter: uniform random in [0, base].
	var frac float64
	if p.rng != nil {
		frac = p.rng.Float64()
	} else {
		frac = rand.Float64() //nolint:gosec // jitter, not crypto
	}
	return time.Duration(frac * base)
}

// ParseRetryAfter parses an HTTP Retry-After header to a duration.
//
// RFC 9110 allows two forms: a non-negative integer delta-seconds,
// or an HTTP-date. Both are accepted. Unparseable input returns nil
// so the caller can fall back to its own backoff policy. Past
// HTTP-date values clamp to 0.
func ParseRetryAfter(header string) *time.Duration {
	return parseRetryAfter(header)
}

// parseRetryAfter is the internal lowercase twin of ParseRetryAfter.
func parseRetryAfter(header string) *time.Duration {
	header = strings.TrimSpace(header)
	if header == "" {
		return nil
	}
	if n, err := strconv.Atoi(header); err == nil {
		if n < 0 {
			n = 0
		}
		d := time.Duration(n) * time.Second
		return &d
	}
	if t, err := http.ParseTime(header); err == nil {
		delta := time.Until(t)
		if delta < 0 {
			delta = 0
		}
		return &delta
	}
	return nil
}
