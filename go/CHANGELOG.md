# Changelog

All notable changes to the `legalize` Go SDK will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
- Typed error tree rooted at `LegalizeError`, with `errors.As`-friendly
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
