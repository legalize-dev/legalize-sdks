# Contributing

## Monorepo layout

```
sdk/
├── openapi.json           ← canonical API spec, synced daily from prod
├── openapi-sdk.json       ← filtered, SDK-only subset (generated)
├── scripts/               ← helpers to fetch + filter the spec, codegen
├── python/                ← Python SDK (PyPI: legalize)
├── node/                  ← reserved for TypeScript SDK (npm: legalize)
├── go/                    ← reserved for Go SDK (github.com/legalize-dev/legalize-sdks/go)
└── curl/                  ← curl snippets and shell helpers
```

Each language directory is self-contained: its own build/test/publish
pipeline. The monorepo exists so all SDKs stay in lockstep with the
shared OpenAPI spec — every SDK is regenerated from the same
`openapi-sdk.json`.

The Go SDK is a Go submodule at `sdk/go/`. Its import path is
`github.com/legalize-dev/legalize-sdks/go` (with `package legalize`
inside, so callers use `legalize.Client{}`). Submodule tags must be
prefixed with the subdirectory — see the release process below.

## Python development

```bash
cd python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Before opening a PR:

```bash
ruff check .
ruff format --check .
mypy --strict src
pytest --cov=legalize --cov-fail-under=95
```

## Syncing the OpenAPI spec

```bash
./scripts/fetch_openapi.sh
./scripts/filter_openapi.py  # writes openapi-sdk.json
./scripts/gen_models.sh       # regenerates python/src/legalize/models/
```

CI runs this daily; if the spec changed a PR is opened automatically.

## Adding a new language

1. Create `sdk/<lang>/` with its own build manifest.
2. Add a CI workflow under `.github/workflows/<lang>-ci.yml`
   (the `node-ci.yml` and `go-ci.yml` templates are working references).
3. Add a publish workflow `<lang>-publish.yml` triggered on the
   language's tag convention.
4. Mirror the coverage + test expectations of the Python SDK.
5. Add the new manifest to `.github/dependabot.yml`.

## Release process

Each SDK is versioned independently and ships through its own publish
workflow. Tag format per language (Go's uses `/` because it is a
submodule and Go's module resolver requires the subdirectory prefix):

- `python-v1.2.3` → `.github/workflows/python-publish.yml` → PyPI (`legalize==1.2.3`)
- `node-v1.2.3`   → `.github/workflows/node-publish.yml`   → npm  (`legalize@1.2.3`)
- `go/v1.2.3`     → `.github/workflows/go-publish.yml`     → Go modules (`github.com/legalize-dev/legalize-sdks/go@v1.2.3`, resolved by `proxy.golang.org` directly from the tagged commit — no registry).

SDK versions track the SDK itself, not the API version. The API version
is negotiated via the `Legalize-API-Version` header per request.

### Release checklist (Python)

Before pushing the tag:

1. Bump in the same PR:
   - `python/pyproject.toml` — `[project] version`
   - `python/src/legalize/_version.py` — `__version__`
   - `python/CHANGELOG.md` — add a `## [X.Y.Z] — YYYY-MM-DD` section
2. Land the PR to `main`.
3. `git tag python-vX.Y.Z <commit> && git push origin python-vX.Y.Z`.

The `python-publish.yml` workflow then:

- cross-checks the tag against `pyproject.toml` and `_version.py`;
- verifies `CHANGELOG.md` has the section;
- re-runs lint + types + offline tests on Python 3.10 / 3.12 / 3.13;
- builds wheel + sdist, smoke-tests the installed wheel;
- publishes to PyPI via **Trusted Publishing (OIDC)** — no long-lived
  tokens — with **PEP 740 attestations** attached to every artifact;
- creates a GitHub Release using the CHANGELOG section as notes and
  attaches the built artifacts.

The `node-publish.yml` workflow follows the same pattern and publishes
with `npm publish --provenance` for sigstore-verifiable builds.

The `go-publish.yml` workflow skips the "publish" step (Go has no
registry — `proxy.golang.org` caches modules straight from the tagged
commit) and instead just creates the GitHub Release with CHANGELOG
notes after CI passes. Tags for the Go submodule must be
`go/vX.Y.Z`, not `go-vX.Y.Z`.

### One-time PyPI Trusted Publishing setup

Do this once per PyPI project, before the first tag on the new workflow:

1. https://pypi.org/manage/project/legalize/settings/publishing/
2. → Add a new trusted publisher → GitHub Actions
3. Owner: `legalize-dev`, Repo: `legalize-sdks`,
   Workflow: `python-publish.yml`, Environment: `pypi`

Once set, the `PYPI_API_TOKEN` secret can be deleted.

### One-time npm setup

1. Create a granular access token on npmjs.com scoped to the `legalize`
   package with publish permission.
2. Save it as the `NPM_TOKEN` GitHub secret.
3. Protect the `npm` environment in GitHub repo settings with required
   reviewers if desired.
