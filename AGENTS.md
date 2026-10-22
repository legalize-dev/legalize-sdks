# SDK instructions

Official Python, Node/TypeScript and Go clients. Read [DEVELOPMENT.md](DEVELOPMENT.md)
for architecture and release procedures, [PARITY.md](PARITY.md) for shared behavior
and [ENVIRONMENT.md](ENVIRONMENT.md) for configuration precedence.

- Check status and branch; preserve existing edits and stage only your own files.
  Keep the human Git author. This public repo must not contain private service
  implementation details.
- Python is the reference implementation. Changes to common API behavior require
  considering all three clients and their parity tests.
- `openapi.json` is filtered into `openapi-sdk.json`; use `scripts/` for model
  generation. Do not hand-edit generated Python models or TypeScript types.
- Use a separate Python environment: installing the engine into the SDK venv
  shadows the `legalize` package. Runtime/library versions are in package metadata.
- Unit tests are offline; integration suites contact the service and need explicit
  credentials. Avoid live calls for ordinary development validation.

## Offline checks

Run these in each affected language's directory, with its development dependencies:

- `python/`: `ruff check .`, `ruff format --check .`, `mypy --strict src`,
  `pytest -m 'not integration' --cov=legalize --cov-fail-under=95`.
- `node/`: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
- `go/`: `go vet ./...`, `go test -race ./...`; additional lint follows current CI.

Releases are tag-triggered, not ordinary pushes to main. Follow the development
guide's per-language version and CHANGELOG updates; inspect current publish
workflows and branch protection before releasing. Do not create release tags as
part of a code-only or documentation task.
