# legalize-go

[![Go Reference](https://pkg.go.dev/badge/github.com/legalize-dev/legalize-sdks/go.svg)](https://pkg.go.dev/github.com/legalize-dev/legalize-sdks/go)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/legalize-dev/legalize-sdks/blob/main/LICENSE)

Official Go client for the [Legalize API](https://legalize.dev/api) — legal texts as structured, versioned data.

```bash
go get github.com/legalize-dev/legalize-sdks/go
```

```go
package main

import (
    "context"
    "fmt"
    "log"

    legalize "github.com/legalize-dev/legalize-sdks/go"
)

func main() {
    client, err := legalize.New() // reads LEGALIZE_API_KEY from env
    if err != nil {
        log.Fatal(err)
    }
    defer client.Close()

    page, err := client.Laws().List(context.Background(), "es", &legalize.LawsListOptions{
        PerPage: legalize.Int(10),
    })
    if err != nil {
        log.Fatal(err)
    }
    for _, law := range page.Results {
        fmt.Println(law.ID, law.Title)
    }
}
```

## Why this SDK

- **Zero dependencies.** Pure `net/http` + stdlib `crypto`. No vendored
  clients, no runtime reflection magic.
- **Typed end-to-end.** Response models match the canonical OpenAPI
  spec. Optional fields are `*T` so callers distinguish "unset" from
  "zero".
- **Retries with backoff.** Honors `Retry-After`, handles 429/5xx,
  exponential delay with jitter. POST and PATCH are *not* retried by
  default (to avoid duplicate side effects).
- **Context-first.** Every method takes `context.Context` for
  cancellation and deadline propagation.
- **Webhook verification is a one-liner.** Constant-time HMAC compare,
  5-minute anti-replay window, clock-skew tolerant.

## Quick tour

### List, iterate, search

```go
ctx := context.Background()

// One page
page, _ := client.Laws().List(ctx, "es", &legalize.LawsListOptions{
    Page:    legalize.Int(1),
    PerPage: legalize.Int(50),
})

// Auto-paginated iterator (fetches pages as needed)
it := client.Laws().Iter(ctx, "es", 100, 0, &legalize.LawsListOptions{
    Status: legalize.String("vigente"),
})
for {
    law, ok, err := it.Next(ctx)
    if err != nil { log.Fatal(err) }
    if !ok { break }
    fmt.Println(law.ID, law.Title)
}

// Full-text search
results, _ := client.Laws().Search(ctx, "es", "protección de datos", nil)
```

### Time travel

Every law has a git-tracked history. Retrieve it at any past revision:

```go
commits, _ := client.Laws().Commits(ctx, "es", "ley_organica_3_2018")
past, _ := client.Laws().AtCommit(ctx, "es", "ley_organica_3_2018",
    commits.Commits[len(commits.Commits)-1].SHA)
fmt.Println(past.ContentMD) // Markdown at that revision
```

### Errors

Every non-2xx response surfaces as a typed error. Match on the
concrete type with `errors.As`:

```go
_, err := client.Laws().Retrieve(ctx, "es", "NOPE")
var notFound *legalize.NotFoundError
var rateLimited *legalize.RateLimitError
switch {
case errors.As(err, &notFound):
    fmt.Println("law missing")
case errors.As(err, &rateLimited):
    time.Sleep(rateLimited.RetryAfter)
case err != nil:
    log.Fatal(err)
}
```

The error tree:

```
LegalizeError
├── APIError
│   ├── AuthenticationError       401
│   ├── ForbiddenError            403
│   ├── NotFoundError             404
│   ├── InvalidRequestError       400
│   ├── ValidationError           422
│   ├── RateLimitError            429 (has .RetryAfter)
│   ├── ServerError               5xx
│   └── ServiceUnavailableError   503
├── APIConnectionError            transport failure
├── APITimeoutError               timeout
└── WebhookVerificationError      bad signature / timestamp
```

### Webhooks

The signing secret for each endpoint is shown **once** on creation.
Store it; there is no recover-the-secret endpoint.

```go
event, err := legalize.Verify(
    body,
    r.Header.Get("X-Legalize-Signature"),
    r.Header.Get("X-Legalize-Timestamp"),
    os.Getenv("LEGALIZE_WHSEC"),
)
if err != nil {
    http.Error(w, "forbidden", http.StatusForbidden)
    return
}
switch event.Type {
case "law.updated":
    // ...
}
```

A full working example is in
[`examples/webhook_server/main.go`](examples/webhook_server/main.go).

### Environment

With `LEGALIZE_API_KEY=leg_...` set, `legalize.New()` is enough. Two
more variables fine-tune behaviour:

| Variable                  | Default                |
|---------------------------|------------------------|
| `LEGALIZE_API_KEY`        | — (required)           |
| `LEGALIZE_BASE_URL`       | `https://legalize.dev` |
| `LEGALIZE_API_VERSION`    | `v1`                   |

Explicit options (`WithAPIKey`, `WithBaseURL`, `WithAPIVersion`) always
win over the environment. Empty strings are treated as unset.

## Configuration

All knobs are functional options on `legalize.New`:

```go
client, err := legalize.New(
    legalize.WithAPIKey("leg_..."),
    legalize.WithBaseURL("https://legalize.dev"),
    legalize.WithAPIVersion("v1"),
    legalize.WithTimeout(30 * time.Second),
    legalize.WithMaxRetries(3),
    legalize.WithRetryPolicy(legalize.RetryPolicy{
        MaxRetries:    3,
        InitialDelay:  500 * time.Millisecond,
        MaxDelay:      30 * time.Second,
        BackoffFactor: 2,
    }),
    legalize.WithHTTPClient(&http.Client{ /* ... */ }),
    legalize.WithDefaultHeaders(http.Header{
        "X-Caller-App": []string{"myapp"},
    }),
)
```

## Examples

See [`examples/`](examples/) for full runnable programs:

- [`list_laws`](examples/list_laws/main.go) — list the first page of Spanish laws
- [`search`](examples/search/main.go) — stream every match for a query
- [`time_travel`](examples/time_travel/main.go) — walk commit history
- [`webhook_server`](examples/webhook_server/main.go) — net/http server verifying signatures

## API reference

Hosted on [pkg.go.dev](https://pkg.go.dev/github.com/legalize-dev/legalize-sdks/go).

## Compatibility

- Go 1.23 or newer.
- No runtime dependencies beyond the Go standard library.
- Tested on darwin, linux and windows.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) in the repository root. PRs
welcome — the SDK tree holds to the cross-SDK parity contract in
[`PARITY.md`](../PARITY.md).

## License

MIT — see [LICENSE](./LICENSE).
