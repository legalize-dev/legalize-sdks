package legalize

import (
	"encoding/json"
	"errors"
	"fmt"
	"strconv"
	"testing"
	"time"
)

const testSecret = "whsec_test_secret_abc123" //nolint:gosec // test fixture, not a real secret

func goodPayload(t *testing.T) []byte {
	t.Helper()
	b, err := json.Marshal(map[string]any{
		"id":         "evt_123",
		"event_type": "law.updated",
		"created_at": "2026-04-20T12:00:00Z",
		"data":       map[string]any{"law_id": "BOE-A-2025-0001"},
	})
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func signedHeaders(t *testing.T, payload []byte, now time.Time) (sig, ts string) {
	t.Helper()
	ts = strconv.FormatInt(now.Unix(), 10)
	sig = ComputeSignature(testSecret, payload, ts)
	return
}

// ---- happy path -------------------------------------------------------

func TestVerify_HappyPath(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	sig, ts := signedHeaders(t, payload, now)
	evt, err := Verify(payload, sig, ts, testSecret, WithReferenceTime(now))
	if err != nil {
		t.Fatal(err)
	}
	if evt.Type != "law.updated" {
		t.Errorf("type %q", evt.Type)
	}
	if evt.ID != "evt_123" {
		t.Errorf("id %q", evt.ID)
	}
}

func TestVerify_MissingHeaderReturnsError(t *testing.T) {
	payload := goodPayload(t)
	_, err := Verify(payload, "", "123", testSecret)
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "missing_header" {
		t.Fatalf("got %v", err)
	}
	_, err = Verify(payload, "v1=abc", "", testSecret)
	if !errors.As(err, &e) || e.Reason != "missing_header" {
		t.Fatalf("got %v", err)
	}
	_, err = Verify(payload, "v1=abc", "123", "")
	if !errors.As(err, &e) || e.Reason != "missing_header" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_BadTimestamp(t *testing.T) {
	payload := goodPayload(t)
	_, err := Verify(payload, "v1=deadbeef", "not-a-number", testSecret)
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "bad_timestamp" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_StaleTimestamp(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	past := now.Add(-10 * time.Minute)
	sig, ts := signedHeaders(t, payload, past)
	_, err := Verify(payload, sig, ts, testSecret, WithReferenceTime(now))
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "timestamp_outside_tolerance" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_ToleranceKnobWidensWindow(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	past := now.Add(-10 * time.Minute)
	sig, ts := signedHeaders(t, payload, past)
	_, err := Verify(payload, sig, ts, testSecret,
		WithReferenceTime(now),
		WithTolerance(20*time.Minute),
	)
	if err != nil {
		t.Fatalf("tolerance knob should have accepted: %v", err)
	}
}

func TestVerify_TamperedBody(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	sig, ts := signedHeaders(t, payload, now)
	tampered := append([]byte{}, payload...)
	tampered[0] = ' ' // mess with the first byte
	_, err := Verify(tampered, sig, ts, testSecret, WithReferenceTime(now))
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "bad_signature" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_WrongSecret(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	sig, ts := signedHeaders(t, payload, now)
	_, err := Verify(payload, sig, ts, "whsec_WRONG", WithReferenceTime(now))
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "bad_signature" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_NoValidSchemeInHeader(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	ts := strconv.FormatInt(now.Unix(), 10)
	_, err := Verify(payload, "v99=abc,v42=def", ts, testSecret, WithReferenceTime(now))
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "no_valid_signature" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_MultiSignatureHeader(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	sig, ts := signedHeaders(t, payload, now)
	// Put the real v1 alongside an extra v1 bogus entry, mixed with
	// a future v99. All v1 entries are checked; one matches.
	multi := "v99=bogus," + sig + ",v1=deadbeefdeadbeefdeadbeefdeadbeef"
	_, err := Verify(payload, multi, ts, testSecret, WithReferenceTime(now))
	if err != nil {
		t.Fatalf("multi-signature should match on the good entry: %v", err)
	}
}

func TestVerify_MalformedSignatureHex(t *testing.T) {
	payload := goodPayload(t)
	now := time.Now()
	ts := strconv.FormatInt(now.Unix(), 10)
	// Provide a v1 signature with invalid hex.
	_, err := Verify(payload, "v1=NOT_HEX!", ts, testSecret, WithReferenceTime(now))
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "bad_signature" {
		t.Fatalf("got %v", err)
	}
}

func TestVerify_NonJSONPayloadFailsPostVerify(t *testing.T) {
	payload := []byte("not json")
	now := time.Now()
	ts := strconv.FormatInt(now.Unix(), 10)
	sig := ComputeSignature(testSecret, payload, ts)
	_, err := Verify(payload, sig, ts, testSecret, WithReferenceTime(now))
	var e *WebhookVerificationError
	if !errors.As(err, &e) || e.Reason != "bad_signature" {
		t.Fatalf("got %v", err)
	}
}

func TestComputeSignature_Stability(t *testing.T) {
	// Known-vector smoke test: signing the same input twice yields the
	// same hex. Mutations flip bits as expected.
	ts := "1700000000"
	payload := []byte(`{"id":"evt_x"}`)
	a := ComputeSignatureHex(testSecret, payload, ts)
	b := ComputeSignatureHex(testSecret, payload, ts)
	if a != b {
		t.Fatal("non-deterministic")
	}
	c := ComputeSignatureHex(testSecret, payload, "1700000001")
	if a == c {
		t.Fatal("timestamp does not affect signature")
	}
	d := ComputeSignatureHex(testSecret+"X", payload, ts)
	if a == d {
		t.Fatal("secret does not affect signature")
	}
}

func TestWebhookVerificationError_Message(t *testing.T) {
	e := &WebhookVerificationError{Reason: "bad_timestamp"}
	if s := e.Error(); s == "" {
		t.Fatal("empty message")
	}
	empty := &WebhookVerificationError{}
	if empty.Error() == "" {
		t.Fatal("empty message")
	}
	_ = fmt.Sprint(e) // shouldn't panic
}
