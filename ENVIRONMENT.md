# Environment variable contract

Cross-SDK specification. Every official Legalize SDK — Python, Node, Go,
and any future language — **MUST** honor this contract so a single
deployment manifest (Kubernetes pod spec, systemd unit, Lambda env,
`.envrc`, etc.) can configure any SDK identically.

## Variables

| Variable | Required | Purpose | Default if unset |
|---|---|---|---|
| `LEGALIZE_API_KEY` | yes | Bearer API key. Must start with `leg_`. | — (client construction fails) |
| `LEGALIZE_BASE_URL` | no | Override the API base URL. Useful for staging, self-hosted, or tests. | `https://legalize.dev` |
| `LEGALIZE_API_VERSION` | no | Pin the `Legalize-API-Version` header sent with every request. | `v1` |

### Reserved (do NOT use yet)

These names are reserved for future use; SDKs should not consume them
today, and integrators should not set them:

- `LEGALIZE_TIMEOUT`
- `LEGALIZE_MAX_RETRIES`
- `LEGALIZE_LOG_LEVEL`

When a reserved variable becomes active, it will be added to the table
above and bumped in each SDK's changelog under a minor version.

## Precedence

```
explicit argument  >  environment variable  >  built-in default
```

1. If the caller passes the value to the client constructor, **that
   wins**, even if the environment variable is set.
2. Otherwise, if the environment variable is set to a non-empty string,
   it is used.
3. Otherwise, the SDK's built-in default applies (see the table).

An empty string (`LEGALIZE_BASE_URL=""`) is treated as **unset** and
falls through to the default. This avoids surprising behaviour when
shell pipelines propagate empty vars.

## Prefix

All SDK-consumed variables **MUST** be prefixed with `LEGALIZE_`.

- No alias shortcuts (`API_KEY`, `BASE_URL` on their own are NEVER
  consumed — too easy to collide with other SDKs in the same pod).
- No alternative casing. Env var names are case-sensitive on Linux and
  the canonical form is UPPER_SNAKE_CASE.

## Zero-config example

With `LEGALIZE_API_KEY=leg_live_...` in the environment:

```python
# Python
from legalize import Legalize
client = Legalize()
```

```typescript
// Node (when the Node SDK ships)
import { Legalize } from "legalize";
const client = new Legalize();
```

```go
// Go (when the Go SDK ships)
import legalize "github.com/legalize-dev/legalize-sdks/go"
client, err := legalize.New()
```

All three above produce an authenticated client pointing at
`https://legalize.dev` using API version `v1`.

## Webhook secrets

Webhook signing secrets are **NOT** part of this contract. They are
per-endpoint (one secret per webhook endpoint you register), not
per-client — so a global `LEGALIZE_WEBHOOK_SECRET` is misleading.

The example integrations in every SDK load their secret from an
application-chosen env var (`LEGALIZE_WHSEC`, `WEBHOOK_SECRET`, etc.) —
that is application convention, not SDK convention.

## Testing

Unit tests must verify:

1. Both variables (`BASE_URL`, `API_VERSION`) fall back to defaults
   when unset.
2. Explicit constructor arguments override the environment.
3. Empty-string env vars are treated as unset.
4. An invalid / missing `LEGALIZE_API_KEY` raises the SDK's
   authentication error before any network I/O.

See `python/tests/unit/test_env_resolution.py` for the reference
implementation.
