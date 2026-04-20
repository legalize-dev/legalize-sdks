package legalize

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"
)

// LegalizeError is the sealed interface that every SDK-raised error
// satisfies. The unexported legalizeError method prevents callers
// outside this package from forging the interface, which keeps
// errors.As checks honest.
type LegalizeError interface {
	error
	legalizeError()
}

// APIError represents any non-2xx HTTP response from the Legalize
// API. It is the base of the typed-error tree. Callers typically
// match on concrete types (AuthenticationError, NotFoundError, ...)
// with errors.As, but raw APIError matches every HTTP-backed error.
type APIError struct {
	// StatusCode is the HTTP status returned by the server.
	StatusCode int
	// Code is the server-provided machine-readable error code. May be
	// empty when the server returned a plain-text or FastAPI body.
	Code string
	// Message is the human-readable error description.
	Message string
	// Body holds the raw response body bytes, kept so callers can
	// inspect server-specific extras (quota info, upgrade URL, ...).
	Body []byte
	// RequestID mirrors the X-Request-Id response header, useful when
	// opening a support ticket.
	RequestID string
	// Response is the underlying HTTP response. Its body is already
	// drained into Body; the response itself is kept so callers can
	// inspect headers (rate limits, etc.).
	Response *http.Response
	// Errors is populated for 422 ValidationError responses with the
	// FastAPI error list.
	Errors []map[string]any
	// Extras captures server-provided quota fields (retry_after,
	// limit, upgrade_url) when the body carries them.
	Extras map[string]any
}

// Error implements the error interface.
func (e *APIError) Error() string {
	var parts []string
	if e.StatusCode != 0 {
		parts = append(parts, fmt.Sprintf("HTTP %d", e.StatusCode))
	}
	if e.Code != "" {
		parts = append(parts, e.Code)
	}
	if e.Message != "" {
		parts = append(parts, e.Message)
	}
	if e.RequestID != "" {
		parts = append(parts, fmt.Sprintf("(request_id=%s)", e.RequestID))
	}
	if len(parts) == 0 {
		return "legalize: unknown API error"
	}
	return strings.Join(parts, " ")
}

func (e *APIError) legalizeError() { _ = e }

// Typed variants. Each embeds *APIError so the common fields and
// Error() method are inherited, but callers can match with errors.As
// to branch on the HTTP semantics.

// AuthenticationError is returned for 401 responses.
type AuthenticationError struct{ *APIError }

// ForbiddenError is returned for 403 responses.
type ForbiddenError struct{ *APIError }

// NotFoundError is returned for 404 responses.
type NotFoundError struct{ *APIError }

// InvalidRequestError is returned for 400 responses.
type InvalidRequestError struct{ *APIError }

// ValidationError is returned for 422 responses (FastAPI schema
// validation failure). The validation issues live in APIError.Errors.
type ValidationError struct{ *APIError }

// RateLimitError is returned for 429 responses. RetryAfter, when
// non-zero, is the server-advised delay before the next attempt.
type RateLimitError struct {
	*APIError
	RetryAfter time.Duration
	Limit      int
}

// ServerError is returned for 5xx responses other than 503.
type ServerError struct{ *APIError }

// ServiceUnavailableError is returned for 503 responses.
type ServiceUnavailableError struct{ *APIError }

// APIConnectionError wraps a transport-layer failure (DNS, connect,
// TLS, reset, ...). It carries the underlying error so callers can
// use errors.Unwrap or errors.Is against stdlib sentinels.
type APIConnectionError struct {
	Cause error
}

// Error implements the error interface.
func (e *APIConnectionError) Error() string {
	if e.Cause != nil {
		return "legalize: connection error: " + e.Cause.Error()
	}
	return "legalize: connection error"
}

// Unwrap exposes the underlying transport error.
func (e *APIConnectionError) Unwrap() error { return e.Cause }

func (e *APIConnectionError) legalizeError() { _ = e }

// APITimeoutError is returned when the request exceeds its context
// deadline or the client-configured timeout without producing a
// response.
type APITimeoutError struct {
	Cause error
}

// Error implements the error interface.
func (e *APITimeoutError) Error() string {
	if e.Cause != nil {
		return "legalize: request timed out: " + e.Cause.Error()
	}
	return "legalize: request timed out"
}

// Unwrap exposes the underlying transport error.
func (e *APITimeoutError) Unwrap() error { return e.Cause }

func (e *APITimeoutError) legalizeError() { _ = e }

// WebhookVerificationError is returned by Verify when a webhook
// payload fails signature or timestamp checks. Reason is one of the
// stable string codes documented on Verify.
type WebhookVerificationError struct {
	Reason string
}

// Error implements the error interface.
func (e *WebhookVerificationError) Error() string {
	if e.Reason == "" {
		return "legalize: webhook verification failed"
	}
	return "legalize: webhook verification failed (" + e.Reason + ")"
}

func (e *WebhookVerificationError) legalizeError() { _ = e }

// ErrorFromResponse inspects a non-2xx *http.Response plus its
// already-read body and returns the most specific LegalizeError
// subtype. The response is kept on the returned APIError so callers
// can still read headers off it.
func ErrorFromResponse(resp *http.Response, body []byte) error {
	base := &APIError{
		StatusCode: resp.StatusCode,
		Body:       body,
		Response:   resp,
		RequestID:  resp.Header.Get("X-Request-Id"),
		Extras:     map[string]any{},
	}

	// Try to parse the JSON body for code/message/extras.
	var data any
	if len(body) > 0 {
		_ = json.Unmarshal(body, &data)
	}
	code, message, extras, errs := parseErrorBody(data)
	base.Code = code
	base.Message = message
	if len(extras) > 0 {
		for k, v := range extras {
			base.Extras[k] = v
		}
	}
	base.Errors = errs

	// Retry-After header fallback when the body did not carry it.
	if _, ok := base.Extras["retry_after"]; !ok {
		if v := parseRetryAfter(resp.Header.Get("Retry-After")); v != nil {
			base.Extras["retry_after"] = *v
		}
	}

	if base.Message == "" {
		if len(body) > 0 {
			trimmed := strings.TrimSpace(string(body))
			if len(trimmed) > 500 {
				trimmed = trimmed[:500]
			}
			base.Message = trimmed
		}
		if base.Message == "" {
			base.Message = fmt.Sprintf("HTTP %d", resp.StatusCode)
		}
	}

	switch resp.StatusCode {
	case 400:
		return &InvalidRequestError{APIError: base}
	case 401:
		return &AuthenticationError{APIError: base}
	case 403:
		return &ForbiddenError{APIError: base}
	case 404:
		return &NotFoundError{APIError: base}
	case 422:
		return &ValidationError{APIError: base}
	case 429:
		rl := &RateLimitError{APIError: base}
		if v, ok := base.Extras["retry_after"]; ok {
			switch n := v.(type) {
			case time.Duration:
				rl.RetryAfter = n
			case float64:
				rl.RetryAfter = time.Duration(n * float64(time.Second))
			case int:
				rl.RetryAfter = time.Duration(n) * time.Second
			case int64:
				rl.RetryAfter = time.Duration(n) * time.Second
			}
		}
		if v, ok := base.Extras["limit"]; ok {
			switch n := v.(type) {
			case float64:
				rl.Limit = int(n)
			case int:
				rl.Limit = n
			case int64:
				rl.Limit = int(n)
			}
		}
		return rl
	case 503:
		return &ServiceUnavailableError{APIError: base}
	}
	if resp.StatusCode >= 500 && resp.StatusCode < 600 {
		return &ServerError{APIError: base}
	}
	return base
}

// parseErrorBody unpacks the three documented server error shapes:
// structured detail dict, FastAPI validation list, or plain string.
func parseErrorBody(data any) (code, message string, extras map[string]any, errs []map[string]any) {
	extras = map[string]any{}

	top, ok := data.(map[string]any)
	if !ok {
		return "", "", extras, nil
	}
	detail, has := top["detail"]
	if !has {
		detail = top
	}

	switch d := detail.(type) {
	case map[string]any:
		code = stringVal(d, "error")
		if code == "" {
			code = stringVal(d, "code")
		}
		message = stringVal(d, "message")
		if message == "" {
			message = stringVal(d, "detail")
		}
		for _, k := range []string{"retry_after", "limit", "upgrade_url"} {
			if v, ok := d[k]; ok {
				extras[k] = v
			}
		}
	case []any:
		for _, item := range d {
			if m, ok := item.(map[string]any); ok {
				errs = append(errs, m)
			}
		}
		if len(errs) > 0 {
			message = stringVal(errs[0], "msg")
			if message == "" {
				message = "validation error"
			}
		} else {
			message = "validation error"
		}
	case string:
		message = d
	}
	return code, message, extras, errs
}

func stringVal(m map[string]any, key string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}
