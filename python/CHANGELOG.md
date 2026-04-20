# Changelog

All notable changes to the Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] — 2026-04-20

### Added

- Environment-variable contract: `Legalize()` with no arguments now
  works when `LEGALIZE_API_KEY` is set. `LEGALIZE_BASE_URL` and
  `LEGALIZE_API_VERSION` are also honored with precedence
  `explicit arg > env var > built-in default`. Empty-string env vars
  fall through to the default. Specified in the top-level
  [`ENVIRONMENT.md`](../ENVIRONMENT.md) and applies to every language SDK.
- `Retry-After` header parsing now accepts the HTTP-date form
  (`Retry-After: Wed, 21 Oct 2025 07:28:00 GMT`) in addition to
  delta-seconds. Per RFC 9110. Past timestamps clamp to zero.
- `WebhookVerificationError` now carries a machine-readable `.reason`
  attribute — one of `missing_header`, `bad_timestamp`,
  `timestamp_outside_tolerance`, `no_valid_signature`, `bad_signature`.
  The public `str(error)` message stays generic so callers can echo
  it back to the sender without leaking which specific check failed.
  Parity with Node and Go SDKs.

### Fixed

- POST and PATCH requests are no longer auto-retried on 429/5xx by
  default. Blindly retrying a non-idempotent request can duplicate
  server-side effects (two webhook endpoints from one
  `webhooks.create` call, two delivery retries from one
  `webhooks.retry`). Callers that know a specific POST is safe to
  retry can opt in with `RetryPolicy(retry_non_idempotent=True)`.
  Brings Python in line with Node and Go SDKs (PARITY.md §5).
- `last_response` is now populated when a request ends in an
  `APIError` (both sync and async). Previously the attribute stayed
  at its old value after 401/403/404/429/5xx, making it impossible
  to read `X-RateLimit-*` and `X-Request-ID` headers on the failing
  response.
- Resource modules no longer form an import cycle with the client.
  Resources depend on a minimal `ClientProtocol` /
  `AsyncClientProtocol` in `resources/_base.py`.

### Changed

- `base_url` and `api_version` on `Legalize` / `AsyncLegalize` are
  now keyword-only with default `None` instead of the hardcoded
  defaults. Existing code that passes values or relies on defaults
  continues to work unchanged.

## [0.1.0] — 2026-04-18

Initial public release. Published to PyPI as
[`legalize`](https://pypi.org/project/legalize/0.1.0/).

### Added

- Sync (`Legalize`) and async (`AsyncLegalize`) clients covering every
  public `/api/v1/*` endpoint.
- Typed Pydantic v2 models generated from the canonical OpenAPI spec.
- `Webhook.verify` — HMAC-SHA256 signature verification with
  constant-time compare and a 5-minute anti-replay window.
- Retry with exponential backoff + jitter. Respects the `Retry-After`
  header; caps server-provided delays at the configured `max_delay`.
- Auto-paginating iterators for laws and reforms (`iter`).
- Typed error hierarchy: `APIError` plus `AuthenticationError`,
  `ForbiddenError`, `NotFoundError`, `InvalidRequestError`,
  `ValidationError`, `RateLimitError`, `ServerError`,
  `ServiceUnavailableError`, `APIConnectionError`, `APITimeoutError`,
  `WebhookVerificationError`.
- `Legalize-API-Version` header on every request for forward
  compatibility.
- Flask and FastAPI example webhook servers, plus CLI-style examples
  for listing, searching, time-travel, stats, and async fan-out.

### Quality

- 280 tests (249 offline + 31 live against `https://legalize.dev`).
- 97.77 % coverage with a 95 % gate.
- `mypy --strict` clean.
- CI matrix: Python 3.10, 3.11, 3.12, 3.13.

[0.1.0]: https://github.com/legalize-dev/legalize-sdks/releases/tag/python-v0.1.0
