# Changelog

All notable changes to the `legalize` Go SDK will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] — 2026-08-21

### Added

- `Laws().AtDate(ctx, country, lawID, date)` — point-in-time retrieval by date. The API resolves the date to a
  version server-side, so callers no longer walk `Laws().Commits()` looking for a SHA
  to hand to `Laws().AtCommit()`. The response carries the resolved `sha` and
  `version_date`, so the answer stays verifiable.

  The rule is **published on or before** the date, not *in force on* it: the
  dates are official publication dates, so a reform still inside its vacatio
  legis resolves as already applying. Cite accordingly.

  `SHA` and `VersionDate` are `*string`: a date before the law existed is a
  valid answer with no version behind it, which is not the same as a version
  whose text came back empty.

## [0.2.0] — 2026-06-17

### Added

- `Client.RequestRaw(ctx, method, path, opts...)` — the low-level
  escape hatch for content negotiation. It fetches any endpoint in a
  non-JSON wire format and returns a `*RawResponse` (`StatusCode`,
  `Content`, `Text`, `ContentType`, `Header`) without decoding the
  body. It reuses the same request path as `Do`, so retries,
  `LastResponse()`, and the typed-error behaviour are identical to the
  JSON path; a non-2xx response returns a nil `*RawResponse` and the
  same typed error.
- `WithFormat(format)` request option controlling the `Accept` header
  for `RequestRaw`: `"xml"` (the default when omitted) sends
  `Accept: application/xml`, `"json"` sends `application/json`, and any
  other value is sent verbatim as the media type (e.g. `"text/xml"`).
  It has no effect on `Do` or the typed resource services.
- `RawResponse` struct. No XML parsing is performed (stdlib only):
  unmarshal `Content` yourself with `encoding/xml` against your own
  type.

The typed resource services still return JSON-parsed models; XML is
opt-in per call via `RequestRaw`. Parity with the Python SDK 0.2.0.

### Changed

- Renamed the sealed error interface from `LegalizeError` to `Error`
  to avoid the `legalize.LegalizeError` stutter (revive). Pre-release
  rename; no published consumers were affected.

## [0.1.0] — 2026-04-20

### Added

- Initial release of the Legalize Go SDK with full parity against
  `PARITY.md` v1.
- `legalize.Client` with zero-config construction from environment
  (`LEGALIZE_API_KEY`, `LEGALIZE_BASE_URL`, `LEGALIZE_API_VERSION`).
- Seven resource services:
  - `Countries`, `Jurisdictions`, `LawTypes`, `Laws`, `Reforms`,
    `Stats`, `Webhooks`.
- Paginated iterators: `LawsIter`, `ReformsIter`, plus `Iter` and
  `SearchIter` helpers on the laws service.
- Typed error tree rooted at `Error`, with `errors.As`-friendly
  `AuthenticationError`, `ForbiddenError`, `NotFoundError`,
  `InvalidRequestError`, `ValidationError`, `RateLimitError`,
  `ServerError`, `ServiceUnavailableError`, `APIConnectionError`,
  `APITimeoutError` and `WebhookVerificationError`.
- Retry policy with exponential backoff + full jitter, honouring
  `Retry-After` as both integer delta-seconds and HTTP-date. POST and
  PATCH are *not* retried by default.
- Webhook signature verification (`legalize.Verify`) — HMAC-SHA256,
  `crypto/subtle.ConstantTimeCompare`, 5-minute anti-replay window,
  multi-signature header support.
- Functional options for every construction knob
  (`WithAPIKey`, `WithBaseURL`, `WithAPIVersion`, `WithTimeout`,
  `WithMaxRetries`, `WithRetryPolicy`, `WithHTTPClient`,
  `WithDefaultHeaders`).
- Raw `Client.Do` escape hatch for endpoints the typed surface has not
  yet wrapped.
- Runnable examples covering list/search/time-travel/webhook-server.
- Tests covering ≥ 95 % of statements, including the cross-SDK
  env-var suite, retry semantics (incl. HTTP-date Retry-After, POST
  not retried), webhook signature vectors (tampered bodies, stale
  timestamps, multi-signature), and a contract test proving every
  operation in `openapi-sdk.json` has an SDK method.
