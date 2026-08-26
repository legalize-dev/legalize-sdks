# Cross-SDK parity specification

Every official Legalize SDK — Python, Node, Go, and any future language —
MUST implement the contract defined in this document. This is the
**single source of truth** for what a Legalize SDK is.

The Python SDK at [`python/`](python/) is the **reference implementation**.
When this document is ambiguous, read the Python source. When Python
and this document disagree, fix whichever is wrong and open a PR to
realign.

---

## Table of contents

1. [Scope](#1-scope)
2. [Client surface](#2-client-surface)
3. [Resources and methods](#3-resources-and-methods)
4. [Error hierarchy](#4-error-hierarchy)
5. [Retry policy](#5-retry-policy)
6. [Pagination](#6-pagination)
7. [Webhook verification](#7-webhook-verification)
8. [Environment-variable contract](#8-environment-variable-contract)
9. [HTTP contract](#9-http-contract)
10. [Testing expectations](#10-testing-expectations)
11. [Packaging and versioning](#11-packaging-and-versioning)
12. [Response formats](#12-response-formats-content-negotiation)

---

## 1. Scope

The API has 18 operations across 7 logical resources plus a health
check. Every SDK MUST expose every operation in the table below with
the canonical method name. No SDK may hide, rename, or shadow a method
without opening an RFC and updating this document.

| Operation | Method | Path | Resource.method |
|---|---|---|---|
| List countries | GET | `/api/v1/countries` | `countries.list()` |
| List jurisdictions | GET | `/api/v1/{country}/jurisdictions` | `jurisdictions.list(country)` |
| List law types | GET | `/api/v1/{country}/law-types` | `law_types.list(country)` |
| List/search laws | GET | `/api/v1/{country}/laws` | `laws.list(country, ...)` (paginated) |
| Retrieve law | GET | `/api/v1/{country}/laws/{id}` | `laws.retrieve(country, law_id)` |
| Law metadata only | GET | `/api/v1/{country}/laws/{id}/meta` | `laws.meta(country, law_id)` |
| Commit history | GET | `/api/v1/{country}/laws/{id}/commits` | `laws.commits(country, law_id)` |
| Law at commit | GET | `/api/v1/{country}/laws/{id}/at/{sha}` | `laws.at_commit(country, law_id, sha)` |
| Law at date | GET | `/api/v1/{country}/laws/{id}/at?date=` | `laws.at_date(country, law_id, date)` |
| Reforms for a law | GET | `/api/v1/{country}/laws/{id}/reforms` | `reforms.list(country, law_id)` |
| Country stats | GET | `/api/v1/{country}/stats` | `stats.retrieve(country)` |
| Create webhook | POST | `/api/v1/webhooks` | `webhooks.create(url, events, ...)` |
| List webhooks | GET | `/api/v1/webhooks` | `webhooks.list()` |
| Retrieve webhook | GET | `/api/v1/webhooks/{id}` | `webhooks.retrieve(endpoint_id)` |
| Update webhook | PATCH | `/api/v1/webhooks/{id}` | `webhooks.update(endpoint_id, ...)` |
| Delete webhook | DELETE | `/api/v1/webhooks/{id}` | `webhooks.delete(endpoint_id)` |
| List deliveries | GET | `/api/v1/webhooks/{id}/deliveries` | `webhooks.deliveries(endpoint_id)` |
| Retry delivery | POST | `/api/v1/webhooks/{id}/deliveries/{did}/retry` | `webhooks.retry(endpoint_id, delivery_id)` |
| Send test event | POST | `/api/v1/webhooks/{id}/test` | `webhooks.test(endpoint_id)` |
| Health check | GET | `/api/health` | (not exposed — monitoring endpoint) |

Convenience methods layered on top (optional but recommended):

- `laws.iter(...)` / `laws.search(...)` / `laws.search_iter(...)` —
  lazy auto-paginated iterators and a full-text-search shortcut.
- `reforms.iter(...)` — same for reforms.
- `webhooks.deliveries_iter(...)` — lazy pagination over deliveries.

Language idioms adapt the naming: Python uses snake_case (`at_commit`),
Node uses camelCase (`atCommit`, `atDate`), Go uses PascalCase on exported
methods (`AtCommit`, `AtDate`). The **semantics stay identical**.

---

## 2. Client surface

Every SDK MUST expose one `Legalize` client type (and, where idiomatic,
an `AsyncLegalize` async twin). Constructor arguments, in order:

- `apiKey` — optional when the environment provides it
- `baseUrl` — optional, default `https://legalize.dev`
- `apiVersion` — optional, default `v1`
- `timeout` — default 30 seconds total
- `maxRetries` / `retry` — retry policy (see §5)
- `defaultHeaders` — extra headers merged into every request
- `transport` — language-appropriate HTTP transport override (for
  tests and custom networking)

Every client MUST also expose:

- `close()` / `Close()` / lifecycle hook for releasing connections.
- `lastResponse` / `LastResponse()` — the raw HTTP response from the
  most recent request, for inspecting `X-RateLimit-*` headers.
- Context-manager or `defer`-friendly cleanup idiom per language.

---

## 3. Resources and methods

The signature source-of-truth is the Python reference implementation
in [`python/src/legalize/resources/`](python/src/legalize/resources/).
Every SDK must expose the same methods with the same parameter names
(translated to the language's casing convention) and the same
semantic behaviour.

### countries

- `countries.list()` → `list[CountryInfo]`

### jurisdictions

- `jurisdictions.list(country)` → `list[JurisdictionInfo]`

### law_types

- `law_types.list(country)` → `list[str]`

### laws

- `laws.list(country, *, page=1, per_page=50, law_type, year, status, jurisdiction, from_date, to_date, sort, text_state)` → `PaginatedLaws`
- `laws.search(country, q, *, page=1, per_page=50, ...)` → `PaginatedLaws`
  (convenience wrapper that sets `q=...`)
- `laws.iter(country, *, per_page=100, limit, ...)` → lazy iterator of `LawSearchResult`
- `laws.search_iter(country, q, *, per_page=100, limit, ...)` → lazy iterator
- `laws.retrieve(country, law_id)` → `LawDetail` (includes `content` Markdown)
- `laws.meta(country, law_id)` → `LawMeta` (no content; fast)
- `laws.commits(country, law_id)` → `CommitsResponse`
- `laws.at_commit(country, law_id, sha)` → `LawAtCommitResponse`
- `laws.at_date(country, law_id, date)` → `LawAtDateResponse`

  `at` is one operation with two addresses: a SHA names a version exactly, a
  date is resolved to one server-side. The response carries the resolved `sha`
  and `version_date` so the answer stays verifiable. The rule is **published on
  or before** the date, not *in force on* it — the dates are official
  publication dates, so a reform inside its vacatio legis resolves as already
  applying. Where the language has nullable types (Go `*string`), `sha` and
  `version_date` are nullable: a date before the law existed is a valid answer
  with no version behind it.

  `text_state` is a filter on **what the body of a law is**, and every listing
  and iterating method must accept it: `list`, `search`, `iter`, `search_iter`.
  It is optional and additive — omitted, the endpoint returns every state, which
  is what it returned before the filter existed. Values are
  `point_in_time` | `current` | `as_enacted` (§3.1). SDKs MUST NOT validate the
  value client-side: the server owns the vocabulary and rejects an unknown one
  with `invalid_text_state`, so a value added later works without an SDK bump.
  Where the language has an idiomatic open union (TypeScript `LawSort`), model
  it the same way; otherwise a plain string.

### reforms

- `reforms.list(country, law_id, *, limit=50, offset=0)` → `ReformsResponse`
- `reforms.iter(country, law_id, *, per_page=100, limit)` → lazy iterator of `Reform`

  `Reform.source_title` names the act that made the change, resolved from
  `source_id` against the corpus, and is nullable — the amending act is not
  always one we serve. How often it is present depends on which text you are
  reading the history of: for an `as_enacted` law 119,915 of Portugal's 120,687
  amendments are named (99.4%), for a `point_in_time` law none of its 9,942 are,
  because a consolidated text's amendments are recorded under the source's own
  revision identifiers rather than law identifiers. SDKs MUST surface the field
  as nullable and MUST NOT document it as usually present without that split.

### stats

- `stats.retrieve(country, *, jurisdiction=None)` → `StatsResponse`

### webhooks

- `webhooks.create(url, events, *, description=None)` → endpoint with one-time secret
- `webhooks.list()` → list of endpoints (secrets redacted)
- `webhooks.retrieve(endpoint_id)` → endpoint
- `webhooks.update(endpoint_id, *, url=None, events=None, description=None, active=None)` → endpoint
- `webhooks.delete(endpoint_id)` → `None`
- `webhooks.deliveries(endpoint_id, *, page=1, per_page=50, status=None)` → page of deliveries
- `webhooks.retry(endpoint_id, delivery_id)` → delivery
- `webhooks.test(endpoint_id)` → test delivery

### 3.1 What the text is, and whether it is still the law

Two response fields answer a question no other field does, and every SDK MUST
carry both on `LawSummary`, `LawSearchResult`, `LawMeta` and `LawDetail`.

**`text_state`** — what the body of the file is (Legalize Format Spec v0.3):

| value | the body is | quotable as the law in force |
|---|---|---|
| `point_in_time` | the law as in force on its date | yes |
| `current` | the latest text the source publishes | yes |
| `as_enacted` | the act as published, amendments not folded in | only if nothing amended it |

Absent means `point_in_time`, which is what 13 of the 14 countries publish, so
SDKs MUST default the field to that rather than to null.

**`text_superseded`** — whether the body is out of date. This is the field a
client decides on: a law can be `status: in_force` and its text still be
superseded. Portugal serves 166,422 of its 171,739 acts as enacted, so this is
not an edge case.

`null` means unknown, and MUST NOT be rendered or treated as `false` — `false`
reads as "safe to quote", which is the expensive direction to be wrong in.

**SDKs MUST NOT compute `text_superseded` themselves**, and MUST NOT document
it as `as_enacted && reform_count > 0`. That formula is wrong on exactly the
laws that matter most: where a source publishes the same act twice — Portugal
does for 338 — the amendment history is recorded against the consolidated copy
and the as-published one reports `reform_count: 0` while being provably stale.
227 of Portugal's laws are that case, including Lei n.º 28/82, amended nine
times. The server resolves it; the field is the answer, and `reform_count` is
the count for *that* record only.

### Response types

All typed responses match the schemas in
[`openapi-sdk.json`](openapi-sdk.json). Generated models live in
`python/src/legalize/models/_generated.py` for Python; Node and Go
generate equivalents into their own `models/` trees and re-export a
curated subset.

---

## 4. Error hierarchy

Every SDK MUST expose the full tree below, with language-appropriate
base type (`Exception` in Python, `Error` in Node, `error` interface
in Go). Field access is through methods in Go, attributes elsewhere.

```
LegalizeError                        (root)
├── APIError                         (any non-2xx HTTP response)
│   ├── AuthenticationError          (401)
│   ├── ForbiddenError               (403)
│   ├── NotFoundError                (404)
│   ├── InvalidRequestError          (400)
│   ├── ValidationError              (422)
│   ├── RateLimitError               (429; .retry_after in seconds)
│   ├── ServerError                  (5xx other than 503)
│   └── ServiceUnavailableError      (503)
├── APIConnectionError               (transport failure, no response)
├── APITimeoutError                  (request exceeded timeout)
└── WebhookVerificationError         (signature/timestamp rejected)
```

Fields on `APIError`:

- `status_code` / `StatusCode()` — HTTP status
- `code` / `Code()` — server-provided error code (string, may be empty)
- `message` / `Message()` — human-readable description
- `body` / `Body()` — raw response body bytes
- `request_id` / `RequestID()` — value of `X-Request-ID` header if
  present (useful when opening a support ticket)

---

## 5. Retry policy

Defaults:

- `max_retries`: **3**
- `initial_delay`: **0.5s**
- `max_delay`: **10s**
- Backoff: exponential — delay(n) = min(`initial_delay * 2^n`, `max_delay`)
- Jitter: full random jitter `[0, delay]` added to every attempt
- `Retry-After` header: honored when present (integer seconds OR
  HTTP-date). Server-provided delay is capped at `max_delay`.

Retry conditions (**retry ONLY when all true**):

1. Attempt number < `max_retries`.
2. Response status is 408, 429, or 5xx — OR — the request raised a
   transport error (connection, timeout).
3. The HTTP method is **idempotent** by default (GET, HEAD, OPTIONS,
   PUT, DELETE). POST and PATCH are **not retried** unless the caller
   explicitly opts in. This prevents duplicate webhook creation and
   duplicate retry-delivery calls.

The SDK MUST log (or expose a hook for logging) the attempt number and
chosen delay before each sleep, so operators can reason about long
tail behaviour.

---

## 6. Pagination

The only paginated endpoint in the current spec is law listing and its
search variant. Reforms and webhook deliveries return a bounded array.

Pagination response fields (`PaginatedLaws`):

- `total` — total matching rows
- `page` — current 1-based page
- `per_page` — size of this page
- `results` — the items on this page
- Optional `count` / `query` / filter echo fields

SDKs MUST expose BOTH:

- `.list(...)` — returns a single page object, fully typed.
- `.iter(...)` — lazy iterator/async iterator yielding one item at a
  time. Fetches the next page only when the current page is exhausted.
  Propagates errors mid-iteration; does not silently swallow.

Caller can pass `per_page` up to 100 (server-enforced upper bound).

---

## 7. Webhook verification

The Legalize server signs outgoing webhook deliveries with HMAC-SHA256
Stripe-style:

- Header `X-Legalize-Signature`: `v1=<hex>` (future schemes may
  comma-join additional versions: `v1=<sig1>,v2=<sig2>`).
- Header `X-Legalize-Timestamp`: unix seconds as a decimal string.
- Header `X-Legalize-Event`: the event type (e.g. `law.updated`).
- Signed content: `f"{timestamp}.{raw_body_bytes}"` — **raw** bytes,
  never a re-serialized JSON string. Reserialization will break the
  signature.
- HMAC key: the endpoint's secret (shown once on creation; never
  reachable by list/retrieve).

`Webhook.verify` contract:

- Inputs: `payload` (raw bytes), `sig_header`, `timestamp`, `secret`,
  optional `tolerance` (default 300 seconds).
- Success: returns a parsed `WebhookEvent` (type, delivery metadata,
  decoded JSON payload).
- Failure: raises/returns `WebhookVerificationError` with a specific
  reason code: `missing_header`, `bad_timestamp`, `timestamp_outside_tolerance`,
  `no_valid_signature`, `bad_signature`.

Implementation requirements:

1. Compare with constant-time HMAC (language-stdlib HMAC compare).
2. Parse the header for ALL `v1=...` entries; accept if ANY matches.
   Reject if zero valid-format entries are present.
3. Compute `abs(now - timestamp)` and reject if > tolerance.
4. Verify the signature **before** parsing JSON — protects against
   JSON-parser resource exhaustion on unauthenticated bodies.
5. Event types currently in use: `law.created`, `law.updated`,
   `law.repealed`, `reform.created`, `test.ping`. SDKs MUST accept
   any string for forward compatibility.

---

## 8. Environment-variable contract

Defined in [`ENVIRONMENT.md`](ENVIRONMENT.md). Summary:

| Variable | Required | Default |
|---|---|---|
| `LEGALIZE_API_KEY` | required if no `apiKey` arg | — |
| `LEGALIZE_BASE_URL` | no | `https://legalize.dev` |
| `LEGALIZE_API_VERSION` | no | `v1` |

Precedence: **explicit arg > env var > default**. Empty string = unset.
Prefix `LEGALIZE_` is mandatory; no aliases.

---

## 9. HTTP contract

Every request MUST send:

- `Authorization: Bearer leg_...` — from the resolved API key.
- `User-Agent: legalize-<lang>/<sdk-version> <lang>/<lang-version> <os>`
  — e.g. `legalize-python/0.1.0 python/3.12.0 darwin`. Node uses
  `legalize-node/...`, Go uses `legalize-go/...`.
- `Legalize-API-Version: v1` — negotiated; can be overridden.
- `Accept: application/json`.
- Custom `default_headers` merged last; caller's `extra_headers` per
  request merge on top of that.

`follow_redirects` is **false** by default. The server does not
redirect; silently following a 301 would hide misconfigurations.

Query parameters:

- `None`/`null`/`nil` values are dropped, not sent as empty strings.
- Booleans serialize to `"true"` / `"false"`.
- Arrays serialize as comma-joined strings (`law_type=ley,rd`).
- Empty arrays are dropped.
- Structured types (Pydantic models, Zod objects, Go structs) are
  **never** accepted as query params — flatten before passing.

---

## 10. Testing expectations

Every SDK MUST ship the following test tiers, using that language's
community-standard framework:

- **unit** — mocked HTTP, fast. Target ≥ 95% line coverage on `src/`.
- **webhooks** — signature vectors (known-good and known-bad payloads,
  timestamp drift, tampered bodies, multiple signatures in one header).
- **property** — at least invariants on retry (backoff monotone capped
  at `max_delay`, never retries beyond `max_retries`, honors
  `Retry-After`) and pagination (iter exhausts exactly `total` items
  across page boundaries).
- **text state** — five checks, because §3.1 is the part a client gets
  wrong on its own: `text_state` reaches the wire from both `list` and
  `search`, **survives every page of `iter` and `search_iter`**, is
  absent from the query string when not asked for, a result decodes
  `text_state` / `reform_count` / `text_superseded`, and a reform
  decodes `source_title`.

  The iterator check is not redundant. The Node SDK shipped `iter` and
  `searchIter` rebuilding their filter object field by field, so
  `textState` was dropped there while `list` and `search` honored it —
  and nothing caught it: every field of the rebuilt object is optional,
  so the compiler saw a valid `LawListOptions`, and the mocked unit
  tests only covered the two methods that were right. It surfaced the
  first time an SDK was pointed at a real server. **Iterators MUST
  forward the filters they were given rather than re-enumerate them**
  (Go copies the options struct; Node spreads it).
- **contract** — validates the SDK covers every `(method, path)` in
  `openapi-sdk.json`. Failing this test means someone added a spec
  endpoint without adding the SDK method.
- **integration** — live read-only tests against production, skipped
  unless `LEGALIZE_API_KEY` and `LEGALIZE_BASE_URL` are set.

Parity reference tests — these MUST have equivalent cases in every
SDK (porting test _names_ is acceptable; porting the exact API is not):

- `test_env_resolution.*` — the env var contract from §8. The Python
  file is [`tests/unit/test_env_resolution.py`](python/tests/unit/test_env_resolution.py).
- Retry honors `Retry-After` integer.
- Retry honors `Retry-After` HTTP-date.
- Retry does NOT retry POST by default.
- Webhook verify rejects tampered body.
- Webhook verify rejects expired timestamp.
- Webhook verify accepts multi-signature header.
- Pagination iter yields exactly `total` items on empty last page.

---

## 11. Packaging and versioning

- **Python** — PyPI `legalize`, tag `python-vX.Y.Z`, Trusted Publishing
  with PEP 740 attestations.
- **Node** — npm `legalize`, tag `node-vX.Y.Z`, `npm publish
  --provenance` with sigstore.
- **Go** — module `github.com/legalize-dev/legalize-sdks/go`, tag
  `go/vX.Y.Z` (submodule prefix required). No registry publish —
  `proxy.golang.org` picks it up from the tag.

SDK version is independent of API version. API version travels in the
`Legalize-API-Version` header per request.

Every SDK ships with:

- `README.md` — hook + install + 60-second tour (laws, time-travel,
  async if applicable, webhooks) + compat matrix + links.
- `CHANGELOG.md` — Keep-a-Changelog format with `## [X.Y.Z] — YYYY-MM-DD`
  sections. The publish workflow verifies the section exists.
- `LICENSE` — MIT, matching repo root.
- `examples/` — at minimum: list laws, search, async (if applicable),
  webhook server integration for the language's dominant framework
  (Python: Flask + FastAPI; Node: Express + Fastify; Go: net/http).

---

## 12. Response formats (content negotiation)

The API serializes every response as JSON by default and as XML when the
client negotiates for it — `Accept: application/xml` (the standard
mechanism) or the `?format=xml` query-param override. JSON stays the
default; no header, `Accept: */*`, or `Accept: application/json` is
unaffected. Error envelopes honor the same negotiation.

The typed resource methods (§3) always request and return JSON. Every SDK
MUST additionally expose a low-level raw primitive for callers who need
another wire format (e.g. an application that speaks XML):

| Language | Primitive |
|---|---|
| Python | `request_raw(method, path, *, params=None, format="xml", extra_headers=None)` (sync + async) |
| Node | `requestRaw(method, path, { params?, format?, extraHeaders?, signal? })` |
| Go | `RequestRaw(ctx, method, path string, opts ...RequestOption)` with the `WithFormat(format)` option |

Contract:

- `format` maps to the `Accept` header: `"xml"` → `application/xml`,
  `"json"` → `application/json`, empty → `application/xml` (the default),
  any other value sent verbatim as the media type.
- The body is returned UNDECODED in a `RawResponse` carrying, at minimum:
  the status code (`status_code` / `statusCode` / `StatusCode`), the raw
  bytes (`content` / `Content`), the decoded `text` / `Text`, the
  `content_type` / `contentType` / `ContentType`, and the response
  `headers` / `Header`.
- The raw primitive reuses the same retry policy, the same `last_response`
  exposure, and raises/returns the SAME typed errors as the JSON path on a
  non-2xx response (the error body is in whatever format was negotiated).
- XML parsing is NOT part of the contract: Python offers a stdlib
  `RawResponse.xml()` convenience; Node and Go expose the raw `text` /
  bytes and leave parsing to the caller (Node ships zero runtime deps, Go
  is stdlib-only). A `json()` convenience is provided where idiomatic.

This keeps the typed surface JSON-only and stable while giving XML-native
consumers a first-class, parity-consistent path.

---

_This document is normative. Contradictions with an SDK implementation
are a bug in the implementation, not in this document, unless explicit
PR discussion concludes otherwise._
