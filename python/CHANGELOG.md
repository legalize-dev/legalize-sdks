# Changelog

All notable changes to the Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Environment-variable contract: `Legalize()` with no arguments now
  works when `LEGALIZE_API_KEY` is set. `LEGALIZE_BASE_URL` and
  `LEGALIZE_API_VERSION` are also honored, with precedence
  `explicit arg > env var > built-in default`. Empty-string env vars
  fall through to the default. The contract is specified in the
  top-level [`ENVIRONMENT.md`](../ENVIRONMENT.md) and applies to every
  language SDK.

### Changed

- `base_url` and `api_version` on `Legalize` / `AsyncLegalize` are now
  keyword-only with default `None` instead of the hardcoded defaults.
  Existing code that passes values or relies on defaults continues to
  work unchanged.

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
