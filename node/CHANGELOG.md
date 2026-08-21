# Changelog

All notable changes to the `@legalize-dev/sdk` Node SDK will be
documented in this file. The format is based on [Keep a Changelog][kac]
and this project adheres to [Semantic Versioning][semver].

[kac]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html

## [Unreleased]

## [0.3.0] — 2026-08-21

### Added

- `laws.atDate(country, lawId, date)` — point-in-time retrieval by date. The API resolves the date to a
  version server-side, so callers no longer walk `laws.commits()` looking for a SHA
  to hand to `laws.atCommit()`. The response carries the resolved `sha` and
  `version_date`, so the answer stays verifiable.

  The rule is **published on or before** the date, not *in force on* it: the
  dates are official publication dates, so a reform still inside its vacatio
  legis resolves as already applying. Cite accordingly.

## [0.2.0] — 2026-06-17

### Added

- `requestRaw(method, path, options?)` on `Legalize` — the low-level
  escape hatch for content negotiation. It fetches any endpoint in a
  non-JSON wire format and returns a `RawResponse` (`.statusCode`,
  `.content` as raw bytes, `.text`, `.contentType`, `.headers`) without
  JSON-decoding. `options.format` controls the `Accept` header:
  `"xml"` (the default) sends `application/xml`, `"json"` sends
  `application/json`, and any other value is used verbatim as the media
  type. Same retry policy, `lastResponse` population, and typed error
  hierarchy as `request`.
- `RawResponse` type, exported from the package, with a `.json()`
  convenience parser. The SDK ships no XML parser and keeps zero runtime
  dependencies — parse `.text`/`.content` with your own library.
- `RequestRawOptions` type and the `formatToAccept` helper are exported.

The typed resource methods still return JSON-parsed models; XML is opt-in
per call via `requestRaw`. See the "Response formats" API docs.

## [0.1.0] — 2026-04-20

### Added

- First public release of the Node SDK for the Legalize API, published
  as [`@legalize-dev/sdk`](https://www.npmjs.com/package/@legalize-dev/sdk)
  on npm.
- `Legalize` client with configurable timeout, retry policy, default
  headers, and `fetch` override for tests.
- Zero-config construction from `LEGALIZE_API_KEY`, `LEGALIZE_BASE_URL`,
  `LEGALIZE_API_VERSION` — matches the cross-SDK `ENVIRONMENT.md`
  contract byte-for-byte with the Python SDK.
- Full resource surface: `countries`, `jurisdictions`, `lawTypes`,
  `laws`, `reforms`, `stats`, `webhooks` (create / list / retrieve /
  update / delete / deliveries / retry / test).
- Auto-paginated async iterators `laws.iter`, `laws.searchIter`,
  `reforms.iter`.
- Typed response models generated from `openapi-sdk.json`.
- Error hierarchy rooted at `LegalizeError`: `APIError`,
  `AuthenticationError`, `ForbiddenError`, `NotFoundError`,
  `InvalidRequestError`, `ValidationError`, `RateLimitError`,
  `ServerError`, `ServiceUnavailableError`, `APIConnectionError`,
  `APITimeoutError`, `WebhookVerificationError`.
- Retry policy with exponential backoff + full jitter. Honors
  `Retry-After` in both delta-seconds and HTTP-date form. POST/PATCH
  are not auto-retried unless `retryNonIdempotent: true`.
- `AbortSignal` support on every method.
- `Webhook.verify` and `Webhook.computeSignature` — constant-time HMAC
  comparison, multi-signature header parsing, 300-second anti-replay
  window.
- Dual ESM + CJS build via `tsup` with `.d.ts` for both variants.
- `await using` / `[Symbol.asyncDispose]` support.
- `lastResponse` populated on success AND error paths for inspecting
  rate-limit headers and `X-Request-Id`.
- Examples for the four main use cases — list laws, search,
  time-travel, Express webhook receiver, Fastify webhook receiver.
- Test suite with ≥ 95% line coverage and a contract test that asserts
  the SDK exposes every `(method, path)` tuple in `openapi-sdk.json`.
