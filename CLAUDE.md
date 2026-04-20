# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Monorepo for official Legalize API client libraries. Each language lives in its own top-level directory, self-contained with its own build/test/publish pipeline. The monorepo exists so all SDKs stay in lockstep with the shared OpenAPI spec at the root (`openapi.json` → filtered to `openapi-sdk.json`).

Current state: Python SDK is the only implementation. `node/` and `go/` are reserved. `curl/` holds shell snippets.

## Commands

All Python commands run from `python/` (CI sets `working-directory: python`):

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# The full PR gate
ruff check .
ruff format --check .
mypy --strict src
pytest --cov=legalize --cov-fail-under=95

# Run a single test file / test
pytest tests/unit/test_retry.py
pytest tests/unit/test_retry.py::test_retries_on_503 -v

# Run by marker (configured in pyproject.toml)
pytest -m unit
pytest -m webhooks
pytest -m property         # Hypothesis
pytest -m contract         # schemathesis
pytest -m integration      # requires LEGALIZE_API_KEY + LEGALIZE_BASE_URL
```

Spec + codegen pipeline (run from repo root):

```bash
./scripts/fetch_openapi.sh    # pulls https://legalize.dev/openapi.json → openapi.json
./scripts/filter_openapi.py   # strips non-SDK paths → openapi-sdk.json
./scripts/gen_models.sh       # regenerates python/src/legalize/models/_generated.py
```

`gen_models.sh` chains the three steps and prefers `python/.venv/bin/datamodel-codegen` when present.

## Architecture

### Python SDK layering

`python/src/legalize/` is intentionally thin and transport-first:

- `_client.py` — `Legalize` (sync) and `AsyncLegalize` (async) share `_BaseClient` for URL building, header assembly, API key validation (`leg_` prefix enforced client-side), and param cleaning. Each subclass wraps its own `httpx.Client`/`AsyncClient`. Both expose a generic `.request(method, path, ...)` plus `.last_response` for rate-limit header inspection.
- `_retry.py` — `RetryPolicy` (exponential backoff, honors `Retry-After`). Resolved through `_resolve_retry_policy`: explicit `retry=` wins over `max_retries=`.
- `_errors.py` — `APIError` hierarchy mapped by status code via `APIError.from_response`.
- `_pagination.py` — cursor pagination helpers used by list endpoints.
- `webhooks.py` — `Webhook.verify(payload, sig_header, timestamp, secret)`. Constant-time comparison, replay window, clock-skew tolerance. Must mirror the server's signature scheme exactly.
- `resources/` — one module per API namespace (`laws`, `countries`, `jurisdictions`, `law_types`, `reforms`, `stats`, `webhooks`). Each module defines a sync class and `Async*` twin. Resources only assemble paths + params; they never build HTTP themselves. `_base.py` exposes the `/api/v1` prefix.
- `models/_generated.py` — Pydantic v2 models produced by `datamodel-codegen`. Do not hand-edit; regenerate via `gen_models.sh`. Ruff/mypy exclude this path (see `pyproject.toml`).

### OpenAPI filter

`scripts/filter_openapi.py` keeps only `/api/v1/*` and `/api/health`, then transitively closes referenced schemas so `openapi-sdk.json` contains only what SDKs need. Everything else (dashboard, admin, billing, sitemaps) is dropped. Generated models stay clean because unreferenced schemas never reach the codegen step.

### Client contracts worth knowing

- Every request sends `Legalize-API-Version` (default `v1`) — SDK version and API version evolve independently.
- Auth is a single `Authorization: Bearer leg_...` header; missing/malformed keys raise `AuthenticationError` before any network call.
- `_clean_params` drops `None`, coerces bools to `"true"/"false"`, comma-joins list/tuple params. Pydantic models are **not** accepted as query params — flatten first.
- `follow_redirects=False` on both transports; the server is not expected to redirect.

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
| `python-ci.yml` | PR + push to `main` touching `python/**` or `openapi-sdk.json` | Lint + matrix test (3.10–3.13) + wheel smoke test |
| `openapi-sync.yml` | Daily 06:00 UTC | Fetch + filter spec, regenerate models, open auto PR if diff |
| `python-integration.yml` | Daily 05:00 UTC | Live read-only tests against prod using `LEGALIZE_API_KEY` secret |
| `python-publish.yml` | Tag `python-v*` push | Verify → test → build → publish to PyPI (Trusted Publishing + PEP 740 attestations) → GitHub release |
| `node-ci.yml` | PR + push touching `node/**` | **Dormant** until the Node SDK lands in `node/` |
| `node-publish.yml` | Tag `node-v*` push | **Dormant** — mirror of the Python flow, publishes to npm with `--provenance` |
| `go-ci.yml` | PR + push touching `go/**` | **Dormant** until the Go SDK lands in `go/` |
| `go-publish.yml` | Tag `go/v*` push | **Dormant** — Go has no registry; workflow validates tag + CHANGELOG, runs tests, creates GitHub Release. `proxy.golang.org` picks the module up automatically |

Release flow (Python): bump `python/pyproject.toml` + `python/src/legalize/_version.py` + `python/CHANGELOG.md` (add `## [X.Y.Z] — YYYY-MM-DD` section) in one PR, land, then push tag `python-vX.Y.Z`. The publish workflow fails closed if any of the three version sources disagree or if CHANGELOG has no matching section. PyPI upload runs via OIDC Trusted Publishing (no long-lived tokens); artifacts carry PEP 740 attestations; a GitHub Release is opened with the CHANGELOG section as notes.

One-time PyPI setup before the first run of the hardened workflow: add a Trusted Publisher on PyPI (repo `legalize-dev/legalize-sdks`, workflow `python-publish.yml`, environment `pypi`). The fallback `PYPI_API_TOKEN` secret can be deleted afterwards.

Per `CONTRIBUTING.md`, each SDK in the monorepo follows the same pattern (`<lang>-ci.yml` + `<lang>-publish.yml`). Tag conventions: `python-vX.Y.Z`, `node-vX.Y.Z`, and `go/vX.Y.Z` (Go uses a slash prefix because it is a Go submodule and the module resolver requires the subdirectory path in the tag — `github.com/legalize-dev/legalize-sdks/go@vX.Y.Z`). SDK versions track the SDK, not the API; API version is negotiated per-request via the `Legalize-API-Version` header.

Supply-chain: `.github/dependabot.yml` opens weekly grouped PRs for GitHub Actions and for the Python dev/runtime stacks (pydantic majors are held back for manual migration). The npm block is commented out and should be uncommented when `node/package.json` exists.

## Conventions

- Python ≥ 3.10. `from __future__ import annotations` everywhere.
- `mypy --strict` on `src/`; tests/examples/generated models are excluded.
- Ruff: line length 100, double quotes, selects `E,F,W,I,B,UP,N,S,RUF`. Tests allow `S105/S106/S311`; generated models ignore `N815/UP`.
- All code, identifiers, commit messages in English (per workspace convention in the parent `legalize/CLAUDE.md`).
- Sync and async APIs must stay symmetric — same resource method names, same error types, same kwargs.
