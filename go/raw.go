package legalize

import (
	"context"
	"net/http"
	"strings"
)

// RawResponse is a raw, non-JSON-decoded API response. It is returned
// by Client.RequestRaw for content negotiation — when you want the
// body in a specific wire format (e.g. XML) instead of the typed JSON
// models the resource services return.
//
// No parsing is performed: unmarshal Content yourself with the
// standard library against your own type, e.g.
//
//	var law lawXML
//	res, err := client.RequestRaw(ctx, "GET", "/api/v1/es/laws/BOE-A-1978-31229")
//	if err != nil { /* ... */ }
//	if err := xml.Unmarshal(res.Content, &law); err != nil { /* ... */ }
type RawResponse struct {
	// StatusCode is the HTTP status of the response. Always 2xx here —
	// non-2xx responses surface as a typed error instead.
	StatusCode int
	// Content is the raw response body bytes. Decode it with
	// encoding/xml, encoding/json, or any decoder you like.
	Content []byte
	// Text is Content decoded to a string (the server charset, by
	// convention UTF-8).
	Text string
	// ContentType is the Content-Type response header value (e.g.
	// "application/xml; charset=utf-8").
	ContentType string
	// Header is the full set of response headers, kept so callers can
	// inspect rate-limit metadata or request IDs.
	Header http.Header
}

// formatToAccept maps a format shorthand to an Accept media type,
// mirroring the Python SDK's _format_to_accept.
//
// "xml" → "application/xml", "json" → "application/json". An empty
// value falls back to XML (the default wire format for RequestRaw).
// Any other value is treated as an explicit media type and returned
// verbatim, so format="text/xml" works too.
func formatToAccept(format string) string {
	switch strings.ToLower(strings.TrimSpace(format)) {
	case "":
		return "application/xml"
	case "xml":
		return "application/xml"
	case "json":
		return "application/json"
	default:
		return format
	}
}

// WithFormat sets the wire format for a RequestRaw call by controlling
// the Accept header. "xml" requests application/xml, "json" requests
// application/json, and any other value is sent verbatim as the media
// type (e.g. "text/xml"). When omitted, RequestRaw defaults to XML.
//
// It has no effect on Do or the typed resource services, which always
// negotiate JSON.
func WithFormat(format string) RequestOption {
	return func(c *requestConfig) { c.format = format }
}

// RequestRaw executes a request and returns the raw, non-JSON-decoded
// body. It is the escape hatch for content negotiation: the typed
// resource services always return JSON models, but RequestRaw lets you
// fetch any endpoint in another wire format (XML by default).
//
// The Accept header is derived from WithFormat — application/xml when
// no WithFormat option is given. WithParams, WithExtraHeaders and
// WithJSONBody are honoured as on Do, and the request flows through the
// same retry path, so LastResponse and the typed-error behaviour are
// identical to the JSON path. A non-2xx response returns a nil
// *RawResponse and the same typed error Do returns (the error body is
// in whatever format you negotiated).
//
//	res, err := client.RequestRaw(ctx, "GET", "/api/v1/es/laws/BOE-A-1978-31229")
//	if err != nil { /* ... */ }
//	xmlText := res.Text // already application/xml
func (c *Client) RequestRaw(ctx context.Context, method, path string, opts ...RequestOption) (*RawResponse, error) {
	cfg := requestConfig{}
	for _, opt := range opts {
		opt(&cfg)
	}

	// Layer the negotiated Accept on top of any caller-supplied extra
	// headers, overriding the default application/json. Caller headers
	// win if they set Accept explicitly.
	headers := http.Header{}
	headers.Set("Accept", formatToAccept(cfg.format))
	for k, vs := range cfg.extraHeaders {
		for _, v := range vs {
			headers.Set(k, v)
		}
	}

	// Reuse the existing request path so retry + lastResponse +
	// typed-error behaviour match Do exactly. We rebuild the option
	// list rather than calling Do with the raw cfg so the Accept
	// override is the last header applied.
	doOpts := []RequestOption{WithExtraHeaders(headers)}
	if cfg.params != nil {
		doOpts = append(doOpts, WithParams(cfg.params))
	}
	if cfg.body != nil {
		doOpts = append(doOpts, WithJSONBody(cfg.body))
	}

	resp, data, err := c.Do(ctx, method, path, doOpts...)
	if err != nil {
		return nil, err
	}
	return &RawResponse{
		StatusCode:  resp.StatusCode,
		Content:     data,
		Text:        string(data),
		ContentType: resp.Header.Get("Content-Type"),
		Header:      resp.Header,
	}, nil
}
