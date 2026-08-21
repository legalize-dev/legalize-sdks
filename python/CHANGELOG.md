# Changelog

All notable changes to the Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] — 2026-08-21

### Added

- `laws.at_date(country, law_id, date)` — point-in-time retrieval by date. The API resolves the date to a
  version server-side, so callers no longer walk `laws.commits()` looking for a SHA
  to hand to `laws.at_commit()`. The response carries the resolved `sha` and
  `version_date`, so the answer stays verifiable.

  The rule is **published on or before** the date, not *in force on* it: the
  dates are official publication dates, so a reform still inside its vacatio
  legis resolves as already applying. Cite accordingly.

## [0.2.1] — 2026-08-19

### Added

- `laws.search_iter(country, *, q, per_page=100, limit=None, ...)` on both
  `Laws` and `AsyncLaws` — auto-paginates across every match of a full-text
  search, the counterpart to `laws.iter()` for listings. The module docstring
  and PARITY.md already promised it; the Node (`searchIter`) and Go
  (`SearchIter`) SDKs already had it.

### Fixed

- `laws.search()` accepts `page`. Without it a search was capped at the first
  `per_page` results (100 at most) with no way to reach the rest, and
  `laws.iter()` only paginates listings, not searches. Requires the API-side
  fix that made `page` effective for searches.

## [0.2.0] — 2026-06-17

### Added

- `request_raw(method, path, *, params=None, format="xml", extra_headers=None)`
  on both `Legalize` and `AsyncLegalize` — the low-level escape hatch for
  content negotiation. It fetches any endpoint in a non-JSON wire format
  and returns a `RawResponse` (`.status_code`, `.content`, `.text`,
  `.content_type`, `.headers`) without JSON-decoding. `format="xml"` (the
  default) sends `Accept: application/xml`, `format="json"` sends
  `application/json`, and any other value is used verbatim as the media
  type.
- `RawResponse.xml()` parses the body into an `xml.etree.ElementTree`
  element (stdlib only); `RawResponse.json()` parses it as JSON.
- `RawResponse` is exported from the top-level `legalize` package.

The typed resource methods still return JSON-parsed models; XML is opt-in
per call via `request_raw`. See the "Response formats" API docs.

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
