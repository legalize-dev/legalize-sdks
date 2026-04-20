# Legalize SDKs

[![python-ci](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml)
[![node-ci](https://github.com/legalize-dev/legalize-sdks/actions/workflows/node-ci.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/node-ci.yml)
[![go-ci](https://github.com/legalize-dev/legalize-sdks/actions/workflows/go-ci.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/go-ci.yml)
[![codeql](https://github.com/legalize-dev/legalize-sdks/actions/workflows/codeql.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/codeql.yml)
[![PyPI](https://img.shields.io/pypi/v/legalize.svg)](https://pypi.org/project/legalize/)
[![npm](https://img.shields.io/npm/v/@legalize-dev/sdk.svg)](https://www.npmjs.com/package/@legalize-dev/sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Official client libraries for the [Legalize API](https://legalize.dev/api) — legal texts as structured, versioned data.

| Language | Package | Source | Tag for release |
|---|---|---|---|
| Python | [`legalize`](https://pypi.org/project/legalize/) on PyPI | [`python/`](python/) | `python-vX.Y.Z` |
| Node / TypeScript | [`@legalize-dev/sdk`](https://www.npmjs.com/package/@legalize-dev/sdk) on npm | [`node/`](node/) | `node-vX.Y.Z` |
| Go | `github.com/legalize-dev/legalize-sdks/go` | [`go/`](go/) | `go/vX.Y.Z` |
| curl | — | [`curl/`](curl/) | — |

All three SDKs share:

- The [cross-SDK parity spec](PARITY.md) — what every SDK must implement.
- The [environment-variable contract](ENVIRONMENT.md) — `LEGALIZE_API_KEY`, `LEGALIZE_BASE_URL`, `LEGALIZE_API_VERSION`, honored byte-for-byte in every language.
- A daily read-only integration run against `https://legalize.dev`.
- CodeQL security scanning, Dependabot, secret-scanning push protection, and pinned third-party actions.

## Quick start

### Python

```bash
pip install legalize
```

```python
from legalize import Legalize

client = Legalize()                       # zero-config — picks up LEGALIZE_API_KEY

for law in client.laws.iter(country="es", law_type="ley_organica"):
    print(law.id, law.title)

results = client.laws.search(country="es", q="protección de datos")
content = client.laws.at_commit(country="es", law_id="ley_organica_3_2018", sha="abc1234")
```

### Node / TypeScript

```bash
npm install @legalize-dev/sdk
```

```ts
import { Legalize } from "@legalize-dev/sdk";

const client = new Legalize();            // zero-config

for await (const law of client.laws.iter("es", { lawType: "ley_organica" })) {
  console.log(law.id, law.title);
}

const results = await client.laws.search("es", "protección de datos");
```

### Go

```bash
go get github.com/legalize-dev/legalize-sdks/go@latest
```

```go
import (
    "context"
    legalize "github.com/legalize-dev/legalize-sdks/go"
)

client, _ := legalize.New()               // zero-config
defer client.Close()

iter := client.Laws().Iter(context.Background(), "es", &legalize.LawsListOptions{
    LawType: []string{"ley_organica"},
})
for {
    law, ok, err := iter.Next(context.Background())
    if err != nil { panic(err) }
    if !ok { break }
    fmt.Println(law.ID, law.Title)
}
```

### Webhook verification (all three)

```python
# Python
from legalize import Webhook
event = Webhook.verify(payload=..., sig_header=..., timestamp=..., secret=...)
```

```ts
// Node
import { Webhook } from "legalize";
const event = Webhook.verify({ payload, sigHeader, timestamp, secret });
```

```go
// Go
event, err := legalize.Verify(payload, sigHeader, timestamp, secret)
```

All three perform constant-time HMAC-SHA256 comparison, enforce a 5-minute replay window, and verify before JSON-parsing.

## Design principles

1. **Typed end-to-end.** Pydantic v2 / TypeScript with `.d.ts` / Go structs — all generated from the same OpenAPI spec.
2. **Minimal surface.** One client per language, one method per endpoint. No magic, no frameworks.
3. **Zero-config when deployed.** Set `LEGALIZE_API_KEY` in the environment; `Legalize()` / `new Legalize()` / `legalize.New()` works with no arguments.
4. **Retries + backoff built in.** Exponential with jitter, honors `Retry-After` (both delta-seconds and HTTP-date). POST/PATCH never retried by default.
5. **Sync + async where idiomatic.** Python has both; Node is promise-based; Go uses `context.Context`.
6. **Webhook verification is a one-liner.** Same scheme across all SDKs; the server signs, the SDK verifies.

## Repository layout

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full tour, release process, and how to add a new language.

## API reference

Full API documentation: <https://legalize.dev/api/docs>.

## License

MIT — see [LICENSE](LICENSE).
