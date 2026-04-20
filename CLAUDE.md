# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Monorepo for official Legalize API client libraries. Each language lives in its own top-level directory, self-contained with its own build/test/publish pipeline. The monorepo exists so all SDKs stay in lockstep with the shared OpenAPI spec at the root (`openapi.json` → filtered to `openapi-sdk.json`).

Current state: three SDKs shipped side-by-side — **Python** (`python/`), **Node/TypeScript** (`node/`), **Go** (`go/`). `curl/` holds shell snippets. Every SDK honors the same OpenAPI contract, the same env-var contract ([`ENVIRONMENT.md`](ENVIRONMENT.md)), and the same parity spec ([`PARITY.md`](PARITY.md)).

## Commands

### Python (from `python/`)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Full offline gate
ruff check . && ruff format --check . && mypy --strict src
pytest -m "not integration" --cov=legalize --cov-fail-under=95

# By marker (pyproject.toml)
pytest -m unit | webhooks | property | contract | vcr | integration
```

### Node (from `node/`)

```bash
npm install

# Full offline gate
npm run lint
npm run typecheck
npm test                   # vitest, excludes tests/integration/
npm run build              # tsup → dist/ (ESM + CJS + .d.ts)

# Live run against prod (needs LEGALIZE_API_KEY)
npm run test:integration   # uses vitest.integration.config.ts
```

### Go (from `go/`)

```bash
go vet ./...
go test -race ./...                     # offline
go test -tags=integration -race ./...   # live, needs LEGALIZE_API_KEY
golangci-lint run                       # uses .golangci.yml (v2 schema)
```

### Spec + codegen (from repo root)

```bash
./scripts/fetch_openapi.sh    # pulls https://legalize.dev/openapi.json → openapi.json
./scripts/filter_openapi.py   # strips non-SDK paths → openapi-sdk.json
./scripts/gen_models.sh       # regenerates python/src/legalize/models/_generated.py

# Node types: from node/
npm run generate:types        # openapi-typescript → src/generated.ts
```

Go structs under `go/generated.go` are currently hand-written to mirror `openapi-sdk.json`; regenerate with `oapi-codegen` when needed.

## Architecture

Python is the **reference implementation**. [`PARITY.md`](PARITY.md) is the cross-SDK spec; when in doubt about any surface, read Python first, then PARITY.md, then the other SDKs.

### Python SDK layering

`python/src/legalize/` is intentionally thin and transport-first:

- `_client.py` — `Legalize` (sync) and `AsyncLegalize` (async) share `_BaseClient` for URL building, header assembly, API key validation (`leg_` prefix enforced client-side), and param cleaning. Each subclass wraps its own `httpx.Client`/`AsyncClient`. Both expose a generic `.request(method, path, ...)` plus `.last_response` for rate-limit header inspection (populated on success AND error).
- `_retry.py` — `RetryPolicy` (exponential backoff, honors `Retry-After` as both delta-seconds and HTTP-date). Resolved through `_resolve_retry_policy`: explicit `retry=` wins over `max_retries=`.
- `_errors.py` — `APIError` hierarchy mapped by status code via `APIError.from_response`.
- `_pagination.py` — offset-based pagination helpers used by list endpoints.
- `webhooks.py` — `Webhook.verify(payload, sig_header, timestamp, secret)`. Constant-time comparison, replay window, clock-skew tolerance. Mirrors the server's Stripe-style `v1=<hex>` scheme exactly.
- `resources/` — one module per API namespace (`laws`, `countries`, `jurisdictions`, `law_types`, `reforms`, `stats`, `webhooks`). Each module defines a sync class and `Async*` twin. Resources depend on a `ClientProtocol` in `_base.py` — not on the concrete client — so the module graph is a DAG (no cyclic imports).
- `models/_generated.py` — Pydantic v2 models produced by `datamodel-codegen`. Do not hand-edit; regenerate via `gen_models.sh`. Ruff/mypy exclude this path.

### Node SDK layering

`node/src/` mirrors Python:

- `client.ts` — the `Legalize` class, promise-based, with fetch-based transport, `lastResponse` populated on success AND error, and `Symbol.asyncDispose` for TS 5.2+ `using` statements.
- `retry.ts`, `errors.ts`, `pagination.ts`, `webhooks.ts`, `env.ts` — direct counterparts to the Python modules.
- `resources/` — camelCased method names (`atCommit`, `lawTypes`), same semantics, TypeScript types from `src/generated.ts` (generated via `openapi-typescript`).
- `tests/integration/` — vitest suite against prod, excluded from `npm test` by the main vitest config, run via `npm run test:integration` with a dedicated config.

### Go SDK layering

`go/` is a submodule at `github.com/legalize-dev/legalize-sdks/go`:

- `client.go` — `Client` struct, functional options (`WithAPIKey`, `WithBaseURL`, ...), `context.Context` on every I/O method, `LastResponse()` accessor.
- `retry.go`, `errors.go`, `pagination.go`, `webhooks.go`, `env.go` — Go-idiomatic mirrors. Error root type is `Error` (sealed interface with an unexported marker); typed variants (`NotFoundError`, `RateLimitError`, ...) embed `*APIError` for `errors.As` precision.
- `countries.go`, `laws.go`, ... — one file per resource, each exposing a `*FooService` with PascalCased methods.
- `generated.go` — response structs mirroring `openapi-sdk.json` (hand-written today; `oapi-codegen`-compatible).
- `integration_test.go` — guarded by `//go:build integration`, runs against prod when `LEGALIZE_API_KEY` is set.

### OpenAPI filter

`scripts/filter_openapi.py` keeps only `/api/v1/*` and `/api/health`, then transitively closes referenced schemas so `openapi-sdk.json` contains only what SDKs need. Everything else (dashboard, admin, billing, sitemaps) is dropped. Generated models stay clean because unreferenced schemas never reach the codegen step.

### Client contracts worth knowing

- Every request sends `Legalize-API-Version` (default `v1`) — SDK version and API version evolve independently.
- Auth is a single `Authorization: Bearer leg_...` header; missing/malformed keys raise `AuthenticationError` before any network call.
- `_clean_params` drops `None`, coerces bools to `"true"/"false"`, comma-joins list/tuple params. Pydantic models are **not** accepted as query params — flatten first.
- `follow_redirects=False` on both transports; the server is not expected to redirect.

### Environment-variable contract

See [`ENVIRONMENT.md`](ENVIRONMENT.md) — canonical cross-SDK spec. Summary:

- `LEGALIZE_API_KEY` (required unless passed explicitly)
- `LEGALIZE_BASE_URL` (default `https://legalize.dev`)
- `LEGALIZE_API_VERSION` (default `v1`)

Precedence: explicit arg > env var > default. Empty-string env is treated as unset. Prefix `LEGALIZE_` is mandatory — no short aliases, to avoid clashes with other SDKs in the same pod. `Legalize()` with zero args is a supported zero-config use case. The resolution helpers live in `_client.py` (`_resolve_api_key` / `_resolve_base_url` / `_resolve_api_version`) and are covered by `tests/unit/test_env_resolution.py`. **When the Node and Go SDKs land, they must honor this contract byte-for-byte.**

## Testing strategy

Unit tests never touch the network. `tests/conftest.py` provides `client`/`aclient` fixtures that plug an `httpx.MockTransport` into the real `Legalize`/`AsyncLegalize` classes, and `retry_client_factory` for tests that need custom retry policies. Test tiers (markers in `pyproject.toml`):

- `unit` — mocked HTTP, fast
- `webhooks` — signature vectors
- `property` — Hypothesis invariants for pagination + retry
- `contract` — schemathesis runs the spec against stub responses
- `vcr` — replays recorded cassettes in `tests/cassettes/`
- `integration` — live staging API; requires env vars, runs in dedicated workflow

Coverage target: 95% (enforced by `pyproject.toml [tool.coverage.report] fail_under`). The `models/` directory is omitted from coverage.

## CI and release

| Workflow | Trigger | Purpose |
|---|---|---|
| `python-ci.yml` | PR + push touching `python/**` or `openapi-sdk.json` | Lint + matrix test (3.10 / 3.11 / 3.12 / 3.13) + wheel smoke test |
| `python-integration.yml` | Daily 05:00 UTC + manual | Live read-only tests against prod using `LEGALIZE_API_KEY` |
| `python-publish.yml` | Tag `python-v*` push | Verify versions/CHANGELOG → test → build → PyPI Trusted Publishing + PEP 740 attestations → GitHub Release |
| `node-ci.yml` | PR + push touching `node/**` or `openapi-sdk.json` | Lint (ESLint flat config) + typecheck + matrix test (Node 20 / 22) + tsup build smoke test |
| `node-integration.yml` | Daily 05:15 UTC + manual | Live integration against prod via dedicated `vitest.integration.config.ts` |
| `node-publish.yml` | Tag `node-v*` push | Verify → test → `npm publish --provenance` (sigstore) → GitHub Release |
| `go-ci.yml` | PR + push touching `go/**` or `openapi-sdk.json` | `go vet` + `gofmt` + `golangci-lint v2` + matrix `go test -race` (Go 1.22 / 1.23 / 1.24) |
| `go-integration.yml` | Daily 05:30 UTC + manual | `go test -tags=integration -race` against prod |
| `go-publish.yml` | Tag `go/v*` push | Verify → test → GitHub Release → warm `proxy.golang.org` (no registry upload — Go modules resolve from the tag) |
| `openapi-sync.yml` | Daily 06:00 UTC + manual | Fetch + filter spec, regenerate models, open auto PR on diff |
| `codeql.yml` | Push + PR + weekly | CodeQL `security-extended` + `security-and-quality` on Python, TypeScript, Go, and Actions workflows |

All workflows declare top-level `permissions: contents: read` and elevate only the jobs that need more (publish → `id-token: write` + `attestations: write`, release → `contents: write`, openapi-sync → `pull-requests: write`). Every third-party action is SHA-pinned.

Release flow per SDK: bump the version file(s) + CHANGELOG in one PR, land, push the tag. The publish workflow fails closed on version mismatch or missing CHANGELOG entry.

- Python: `python/pyproject.toml` + `python/src/legalize/_version.py` + `python/CHANGELOG.md`, tag `python-vX.Y.Z`.
- Node: `node/package.json` + `node/CHANGELOG.md`, tag `node-vX.Y.Z`.
- Go: `go/version.go` + `go/CHANGELOG.md`, tag `go/vX.Y.Z` (the `go/` prefix is mandatory — Go's submodule resolver requires it).

SDK versions track the SDK, not the API. API version is negotiated per-request via `Legalize-API-Version` (default `v1`, overridable via `LEGALIZE_API_VERSION`).

Supply-chain: `.github/dependabot.yml` opens weekly grouped PRs for GitHub Actions, pip (`/python`), npm (`/node`), and gomod (`/go`). Pydantic majors are held back for manual migration. Secret scanning + push protection + Dependabot security updates are enabled at the repo level.

## Conventions

- Python ≥ 3.10, `mypy --strict` on `src/`, ruff line length 100, `from __future__ import annotations` everywhere. Tests allow `S105/S106/S311`; generated models ignore `N815/UP`.
- Node ≥ 20, TypeScript 5.4+, strict mode, ESLint flat config, ESM + CJS dual build via tsup, zero runtime deps.
- Go ≥ 1.22 (matrix tests 1.22/1.23/1.24), stdlib only, `context.Context` first on every I/O, functional options. golangci-lint config is v2 schema (run via `golangci/golangci-lint-action@v9`).
- All code, identifiers, commit messages in English (per workspace convention in the parent `legalize/CLAUDE.md`).
- Sync and async APIs must stay symmetric — same resource method names, same error types, same kwargs.
- Every SDK-surface change must keep PARITY.md in sync. Changing a method signature in Python requires the same change across Node and Go.
