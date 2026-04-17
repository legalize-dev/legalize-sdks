# Changelog

All notable changes to the Python SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial release of the Python SDK.
- Sync (`Legalize`) and async (`AsyncLegalize`) clients covering every
  public `/api/v1/*` endpoint.
- Typed Pydantic models generated from the OpenAPI spec.
- `Webhook.verify` for HMAC-SHA256 signature verification with
  replay protection.
- Retry with exponential backoff + jitter, respecting `Retry-After`.
- Auto-paginating iterators for laws and reforms.
- Typed error hierarchy (`APIError`, `AuthenticationError`,
  `RateLimitError`, etc.).
