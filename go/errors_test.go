package legalize

import (
	"errors"
	"net/http"
	"strings"
	"testing"
)

func mkResp(status int, headers http.Header, body []byte) *http.Response {
	r := &http.Response{
		StatusCode: status,
		Header:     headers,
	}
	if r.Header == nil {
		r.Header = http.Header{}
	}
	r.Body = http.NoBody
	_ = body
	return r
}

func TestErrorFromResponse_401(t *testing.T) {
	r := mkResp(401, nil, nil)
	body := []byte(`{"detail":{"error":"invalid_api_key","message":"bad key"}}`)
	err := ErrorFromResponse(r, body)
	var ae *AuthenticationError
	if !errors.As(err, &ae) {
		t.Fatalf("want AuthenticationError, got %T", err)
	}
	if ae.Code != "invalid_api_key" {
		t.Errorf("code: %q", ae.Code)
	}
	if ae.Message != "bad key" {
		t.Errorf("msg: %q", ae.Message)
	}
}

func TestErrorFromResponse_403(t *testing.T) {
	err := ErrorFromResponse(mkResp(403, nil, nil), []byte(`{"detail":"forbidden"}`))
	var fe *ForbiddenError
	if !errors.As(err, &fe) {
		t.Fatalf("want ForbiddenError, got %T", err)
	}
}

func TestErrorFromResponse_404_StringDetail(t *testing.T) {
	err := ErrorFromResponse(mkResp(404, nil, nil), []byte(`{"detail":"not found: xyz"}`))
	var nf *NotFoundError
	if !errors.As(err, &nf) {
		t.Fatalf("want NotFoundError, got %T", err)
	}
	if !strings.Contains(nf.Message, "not found") {
		t.Errorf("msg: %q", nf.Message)
	}
}

func TestErrorFromResponse_400_InvalidRequest(t *testing.T) {
	err := ErrorFromResponse(mkResp(400, nil, nil), []byte(`{"detail":"bad"}`))
	var ire *InvalidRequestError
	if !errors.As(err, &ire) {
		t.Fatalf("want InvalidRequestError, got %T", err)
	}
}

func TestErrorFromResponse_422_Validation(t *testing.T) {
	body := []byte(`{"detail":[{"loc":["q"],"msg":"field required","type":"value_error"}]}`)
	err := ErrorFromResponse(mkResp(422, nil, nil), body)
	var ve *ValidationError
	if !errors.As(err, &ve) {
		t.Fatalf("want ValidationError, got %T", err)
	}
	if len(ve.Errors) != 1 || ve.Errors[0]["msg"] != "field required" {
		t.Errorf("errors: %+v", ve.Errors)
	}
	if ve.Message != "field required" {
		t.Errorf("msg: %q", ve.Message)
	}
}

func TestErrorFromResponse_429_WithRetryAfterHeader(t *testing.T) {
	h := http.Header{}
	h.Set("Retry-After", "7")
	err := ErrorFromResponse(mkResp(429, h, nil), []byte(`{"detail":{"error":"quota_exceeded","limit":10000}}`))
	var rle *RateLimitError
	if !errors.As(err, &rle) {
		t.Fatalf("want RateLimitError, got %T", err)
	}
	if rle.Limit != 10000 {
		t.Errorf("limit: %d", rle.Limit)
	}
	if rle.RetryAfter.Seconds() != 7 {
		t.Errorf("retry-after: %v", rle.RetryAfter)
	}
}

func TestErrorFromResponse_503(t *testing.T) {
	err := ErrorFromResponse(mkResp(503, nil, nil), []byte(`{"detail":"maintenance"}`))
	var su *ServiceUnavailableError
	if !errors.As(err, &su) {
		t.Fatalf("want ServiceUnavailableError, got %T", err)
	}
}

func TestErrorFromResponse_500_Generic(t *testing.T) {
	err := ErrorFromResponse(mkResp(502, nil, nil), nil)
	var se *ServerError
	if !errors.As(err, &se) {
		t.Fatalf("want ServerError, got %T", err)
	}
}

func TestErrorFromResponse_UnknownStatus(t *testing.T) {
	err := ErrorFromResponse(mkResp(418, nil, nil), []byte(`teapot`))
	var ae *APIError
	if !errors.As(err, &ae) {
		t.Fatalf("want APIError, got %T", err)
	}
	// Not one of the typed subclasses.
	var nf *NotFoundError
	if errors.As(err, &nf) {
		t.Fatal("418 must not be NotFoundError")
	}
}

func TestAPIError_StringFormatsAllParts(t *testing.T) {
	e := &APIError{StatusCode: 429, Code: "quota_exceeded", Message: "hit cap", RequestID: "req_x"}
	s := e.Error()
	if !strings.Contains(s, "HTTP 429") || !strings.Contains(s, "quota_exceeded") ||
		!strings.Contains(s, "hit cap") || !strings.Contains(s, "req_x") {
		t.Errorf("error message: %q", s)
	}
}

func TestAPIError_EmptyString(t *testing.T) {
	e := &APIError{}
	if e.Error() == "" {
		t.Fatal("empty error message")
	}
}

func TestConnectionError_UnwrapsCause(t *testing.T) {
	base := errors.New("tls bad cert")
	e := &APIConnectionError{Cause: base}
	if !errors.Is(e, base) {
		t.Error("errors.Is should walk to cause")
	}
	if e.Error() == "" {
		t.Error("message empty")
	}
	blank := &APIConnectionError{}
	if blank.Error() == "" {
		t.Error("blank message")
	}
}

func TestTimeoutError_UnwrapsCause(t *testing.T) {
	base := errors.New("deadline")
	e := &APITimeoutError{Cause: base}
	if !errors.Is(e, base) {
		t.Error("unwrap")
	}
	blank := &APITimeoutError{}
	if blank.Error() == "" {
		t.Error("blank message")
	}
}

func TestLegalizeErrorInterface_MarkerPreventsForgery(t *testing.T) {
	// Smoke: our typed errors implement LegalizeError.
	var le LegalizeError = &APIError{}
	_ = le
	le = &AuthenticationError{APIError: &APIError{}}
	_ = le
	le = &APIConnectionError{}
	_ = le
	le = &APITimeoutError{}
	_ = le
	le = &WebhookVerificationError{}
	_ = le
}

func TestErrorFromResponse_RetryAfterFromHeaderPopulatesExtras(t *testing.T) {
	h := http.Header{}
	h.Set("Retry-After", "9")
	err := ErrorFromResponse(mkResp(429, h, nil), nil)
	var rle *RateLimitError
	if !errors.As(err, &rle) {
		t.Fatalf("want RateLimitError, got %T", err)
	}
	if rle.RetryAfter.Seconds() != 9 {
		t.Errorf("retry-after: %v", rle.RetryAfter)
	}
}

func TestErrorFromResponse_RequestIDHeader(t *testing.T) {
	h := http.Header{}
	h.Set("X-Request-Id", "req_abc123")
	err := ErrorFromResponse(mkResp(404, h, nil), []byte(`{"detail":"nope"}`))
	var nf *NotFoundError
	if !errors.As(err, &nf) {
		t.Fatal("want NotFoundError")
	}
	if nf.RequestID != "req_abc123" {
		t.Errorf("request id: %q", nf.RequestID)
	}
}

func TestErrorFromResponse_FallbackMessageFromBody(t *testing.T) {
	err := ErrorFromResponse(mkResp(500, nil, nil), []byte("  plain text error  "))
	var se *ServerError
	if !errors.As(err, &se) {
		t.Fatal("want ServerError")
	}
	if !strings.Contains(se.Message, "plain text error") {
		t.Errorf("msg: %q", se.Message)
	}
}

func TestErrorFromResponse_FallbackWhenBodyEmpty(t *testing.T) {
	err := ErrorFromResponse(mkResp(500, nil, nil), nil)
	var se *ServerError
	if !errors.As(err, &se) {
		t.Fatal("want ServerError")
	}
	if se.Message != "HTTP 500" {
		t.Errorf("msg: %q", se.Message)
	}
}
