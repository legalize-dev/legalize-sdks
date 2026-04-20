# Legalize SDKs

[![python-ci](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/legalize.svg)](https://pypi.org/project/legalize/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Official client libraries for the [Legalize API](https://legalize.dev/api).

| Language | Package | Source | Status |
|---|---|---|---|
| Python | [`legalize`](https://pypi.org/project/legalize/) | [`python/`](python/) | In development |
| Node / TS | `legalize` (npm) | planned | Not started |
| Go | `github.com/legalize-dev/legalize-sdks/go` | [`go/`](go/) | Not started |
| curl | — | [`curl/`](curl/) | Planned |

## Quick start (Python)

```bash
pip install legalize
```

```python
from legalize import Legalize

client = Legalize(api_key="leg_...")

# Iterate every law for Spain, auto-paginated
for law in client.laws.list(country="es", law_type="ley_organica"):
    print(law.id, law.title)

# Search
results = client.laws.search(country="es", q="protección de datos")

# Time-travel
content = client.laws.at_commit(country="es", law_id="ley_organica_3_2018", sha="abc1234")

# Verify a webhook
from legalize.webhooks import Webhook

event = Webhook.verify(
    payload=request.body,
    sig_header=request.headers["X-Legalize-Signature"],
    timestamp=request.headers["X-Legalize-Timestamp"],
    secret=os.environ["LEGALIZE_WHSEC"],
)
```

## Design principles

1. **Typed end-to-end.** Python: `mypy --strict` + `py.typed`. Models are
   Pydantic, generated from the canonical OpenAPI spec.
2. **Minimal surface.** One `Legalize` client. One method per endpoint.
   No magic, no frameworks.
3. **Sync by default, async when you need it.** `Legalize` is sync.
   `AsyncLegalize` is async. Same resource API, same error types.
4. **Retries + backoff built in.** Respects `Retry-After`. Configurable.
5. **Webhook verification is a one-liner.** Constant-time comparison,
   replay window, clock-skew tolerance. Mirrors the server exactly.

## Repository layout

See [CONTRIBUTING.md](CONTRIBUTING.md).

## API reference

Full API documentation: <https://legalize.dev/api/docs>.

## License

MIT — see [LICENSE](LICENSE).
