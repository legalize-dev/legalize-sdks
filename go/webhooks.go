package legalize

import (
	"crypto/hmac"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"math"
	"strconv"
	"strings"
	"time"
)

// DefaultWebhookTolerance is the default allowable clock drift
// between the signed timestamp and the verifier's wall clock. Five
// minutes matches the server defaults and the Python / Node SDKs.
const DefaultWebhookTolerance = 5 * time.Minute

// supportedSchemes lists the signature-version prefixes the SDK
// accepts today. Future schemes will be added here; unknown prefixes
// are silently ignored per the Stripe-style scheme.
var supportedSchemes = map[string]struct{}{"v1": {}}

// WebhookEvent is the parsed payload of a verified webhook delivery.
type WebhookEvent struct {
	ID        string          `json:"id"`
	Type      string          `json:"type"`
	CreatedAt string          `json:"created_at"`
	Data      json.RawMessage `json:"data"`
	Raw       json.RawMessage `json:"-"`
}

// VerifyOption tunes Verify's behaviour.
type VerifyOption func(*verifyConfig)

type verifyConfig struct {
	tolerance time.Duration
	now       time.Time
}

// WithTolerance overrides the default ±5 minute clock drift window.
func WithTolerance(d time.Duration) VerifyOption {
	return func(c *verifyConfig) { c.tolerance = d }
}

// WithReferenceTime lets tests inject a deterministic wall clock.
// Real integrations should leave this unset.
func WithReferenceTime(t time.Time) VerifyOption {
	return func(c *verifyConfig) { c.now = t }
}

// Verify checks a webhook signature and returns the parsed event.
//
// Inputs are the raw request body (not a re-serialised JSON), the
// X-Legalize-Signature header, the X-Legalize-Timestamp header, and
// the endpoint's signing secret.
//
// On failure it returns a *WebhookVerificationError whose Reason is
// one of: "missing_header", "bad_timestamp", "timestamp_outside_tolerance",
// "no_valid_signature", "bad_signature".
//
// The signature is compared with crypto/subtle.ConstantTimeCompare.
// Verification happens BEFORE the JSON body is parsed, protecting
// against JSON-parser resource exhaustion on unauthenticated bodies.
func Verify(payload []byte, sigHeader, timestamp, secret string, opts ...VerifyOption) (*WebhookEvent, error) {
	cfg := verifyConfig{tolerance: DefaultWebhookTolerance}
	for _, opt := range opts {
		opt(&cfg)
	}

	if sigHeader == "" || timestamp == "" || secret == "" {
		return nil, &WebhookVerificationError{Reason: "missing_header"}
	}

	// Timestamp parse.
	tsInt, err := strconv.ParseInt(strings.TrimSpace(timestamp), 10, 64)
	if err != nil {
		return nil, &WebhookVerificationError{Reason: "bad_timestamp"}
	}

	reference := cfg.now
	if reference.IsZero() {
		reference = time.Now()
	}
	diff := reference.Unix() - tsInt
	if math.Abs(float64(diff)) > cfg.tolerance.Seconds() {
		return nil, &WebhookVerificationError{Reason: "timestamp_outside_tolerance"}
	}

	// Compute expected signature.
	expectedHex := ComputeSignatureHex(secret, payload, timestamp)
	expectedBytes, err := hex.DecodeString(expectedHex)
	if err != nil {
		// Shouldn't happen — we control the producer.
		return nil, &WebhookVerificationError{Reason: "bad_signature"}
	}

	candidates := extractSchemeHexes(sigHeader)
	if len(candidates) == 0 {
		return nil, &WebhookVerificationError{Reason: "no_valid_signature"}
	}

	matched := false
	for _, cand := range candidates {
		candBytes, err := hex.DecodeString(cand)
		if err != nil {
			continue
		}
		if subtle.ConstantTimeCompare(candBytes, expectedBytes) == 1 {
			matched = true
			break
		}
	}
	if !matched {
		return nil, &WebhookVerificationError{Reason: "bad_signature"}
	}

	// Parse JSON payload AFTER verification succeeds.
	var raw map[string]any
	if err := json.Unmarshal(payload, &raw); err != nil {
		return nil, &WebhookVerificationError{Reason: "bad_signature"}
	}

	evt := &WebhookEvent{Raw: payload}
	if v, ok := raw["id"].(string); ok {
		evt.ID = v
	}
	if v, ok := raw["event_type"].(string); ok {
		evt.Type = v
	} else if v, ok := raw["type"].(string); ok {
		evt.Type = v
	}
	if v, ok := raw["created_at"].(string); ok {
		evt.CreatedAt = v
	}
	if d, ok := raw["data"]; ok {
		if b, err := json.Marshal(d); err == nil {
			evt.Data = b
		}
	}
	return evt, nil
}

// ComputeSignatureHex returns the canonical hex signature for the
// given (secret, payload, timestamp). Exposed so tests can build
// known-good signature vectors and callers can implement custom flows.
func ComputeSignatureHex(secret string, payload []byte, timestamp string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(timestamp))
	mac.Write([]byte("."))
	mac.Write(payload)
	return hex.EncodeToString(mac.Sum(nil))
}

// ComputeSignature returns the "v1=<hex>" header-ready signature.
func ComputeSignature(secret string, payload []byte, timestamp string) string {
	return "v1=" + ComputeSignatureHex(secret, payload, timestamp)
}

// extractSchemeHexes parses an X-Legalize-Signature header for every
// supported "vN=<hex>" pair. Unknown schemes are ignored; a malformed
// or empty header yields no candidates (and the caller MUST treat
// that as a verification failure).
func extractSchemeHexes(header string) []string {
	var out []string
	for _, part := range strings.Split(header, ",") {
		part = strings.TrimSpace(part)
		scheme, value, ok := strings.Cut(part, "=")
		if !ok {
			continue
		}
		if _, ok := supportedSchemes[scheme]; !ok {
			continue
		}
		value = strings.TrimSpace(value)
		if value == "" {
			continue
		}
		out = append(out, value)
	}
	return out
}
