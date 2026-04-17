# Contributing

## Monorepo layout

```
sdk/
├── openapi.json           ← canonical API spec, synced daily from prod
├── scripts/               ← helpers to fetch + filter the spec, codegen
├── python/                ← Python SDK (PyPI: legalize)
├── node/                  ← reserved for TypeScript SDK (npm: legalize)
├── go/                    ← reserved for Go SDK
└── curl/                  ← curl snippets and shell helpers
```

Each language directory is self-contained: its own build/test/publish
pipeline. The monorepo exists so all SDKs stay in lockstep with the
shared OpenAPI spec.

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
2. Add a CI workflow under `.github/workflows/<lang>-ci.yml`.
3. Add a publish workflow `<lang>-publish.yml` triggered on tags like
   `<lang>-vX.Y.Z`.
4. Mirror the coverage + test expectations of the Python SDK.

## Release process

Each SDK is versioned independently. Tag format:
- `python-v1.2.3` → publishes `legalize==1.2.3` to PyPI
- `node-v1.2.3` → publishes `legalize@1.2.3` to npm
- `go-v1.2.3` → tags the Go module

SDK versions track the SDK itself, not the API version. The API version
is negotiated via the `Legalize-API-Version` header per request.
