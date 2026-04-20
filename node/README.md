# legalize

[![npm](https://img.shields.io/npm/v/legalize.svg)](https://www.npmjs.com/package/legalize)
[![Node](https://img.shields.io/node/v/legalize.svg)](https://www.npmjs.com/package/legalize)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/legalize-dev/legalize-sdks/blob/main/LICENSE)

Official Node client for the [Legalize API](https://legalize.dev/api) — legal texts as structured, versioned data.

```bash
npm install legalize
```

```ts
import { Legalize } from "legalize";

const client = new Legalize({ apiKey: "leg_..." });

for await (const law of client.laws.iter("es", { lawType: "ley_organica" })) {
  console.log(law.id, law.title);
}
```

## Why this SDK

- **Typed end-to-end.** Types are generated from the canonical OpenAPI
  spec and shipped in the package. `strict` TypeScript friendly.
- **Zero runtime dependencies.** Uses Node's built-in `fetch`,
  `AbortController`, and `crypto`. No `undici`, `axios`, or `node-fetch`.
- **Retries with backoff built in.** Honors `Retry-After`, handles
  429/5xx, exponential delay with full jitter, and never auto-retries
  POST/PATCH by default (no duplicate mutations).
- **Webhook verification is a one-liner.** Constant-time HMAC compare,
  5-minute anti-replay window, clock-skew tolerant.
- **Works in any Node 20+ environment.** Lambda, Cloud Functions, Fly,
  Railway, plain `node`, `tsx`, `ts-node`, etc.
- **ESM and CJS dual build.** `"type": "module"` with a proper `exports`
  map so `import` and `require` both resolve cleanly.

## Quick tour

### List, iterate, search

```ts
// One page
const page = await client.laws.list("es", { page: 1, perPage: 50 });
console.log(page.total, page.results.length);

// Auto-paginated async iterator (fetches pages as needed)
for await (const law of client.laws.iter("es", { status: "vigente" })) {
  // ...
}

// Full-text search
const results = await client.laws.search("es", "protección de datos");
```

### Time-travel

Every law has a git-tracked history. Retrieve it at any past revision:

```ts
const commits = await client.laws.commits("es", "ley_organica_3_2018");
const oldest = commits.commits[commits.commits.length - 1]!.sha;
const past = await client.laws.atCommit("es", "ley_organica_3_2018", oldest);
console.log(past.content_md); // Markdown at that revision
```

### Abort + timeout

Every method accepts a standard `AbortSignal`:

```ts
const ac = new AbortController();
setTimeout(() => ac.abort(), 5000);
const out = await client.laws.list("es", { signal: ac.signal });
```

Per-request timeouts are configured on the client:

```ts
const client = new Legalize({ apiKey: "leg_...", timeout: 10_000 });
```

### Webhooks

Verify a signed delivery in one call. **Pass the raw request bytes** —
re-serialized JSON will NOT verify:

```ts
import express from "express";
import { Webhook, WebhookVerificationError } from "legalize";

app.post(
  "/webhooks/legalize",
  express.raw({ type: "application/json" }),
  (req, res) => {
    try {
      const event = Webhook.verify({
        payload: req.body as Buffer,
        sigHeader: req.header("X-Legalize-Signature") ?? "",
        timestamp: req.header("X-Legalize-Timestamp") ?? "",
        secret: process.env.LEGALIZE_WHSEC!,
      });
      if (event.type === "law.updated") {
        // ...
      }
      res.status(204).send();
    } catch (err) {
      if (err instanceof WebhookVerificationError) {
        res.status(400).send();
        return;
      }
      throw err;
    }
  },
);
```

Working Express and Fastify receivers in
[`examples/`](https://github.com/legalize-dev/legalize-sdks/tree/main/node/examples).

## Configuration

### Zero-config (recommended for servers + Kubernetes)

Set the environment and just instantiate:

```bash
export LEGALIZE_API_KEY=leg_live_...
# Optional:
export LEGALIZE_BASE_URL=https://legalize.dev
export LEGALIZE_API_VERSION=v1
```

```ts
import { Legalize } from "legalize";

const client = new Legalize(); // picks everything up from the environment
```

### Explicit

```ts
import { Legalize, RetryPolicy } from "legalize";

const client = new Legalize({
  apiKey: "leg_...",
  baseUrl: "https://legalize.dev",
  apiVersion: "v1",         // negotiated via Legalize-API-Version header
  timeout: 30_000,          // milliseconds
  retry: new RetryPolicy({
    maxRetries: 5,
    initialDelay: 0.5,
    maxDelay: 10,
  }),
  defaultHeaders: { "X-Correlation-Id": "..." },
});
```

Precedence: explicit argument > environment variable > built-in default.
The full cross-SDK contract is documented in
[`ENVIRONMENT.md`](https://github.com/legalize-dev/legalize-sdks/blob/main/ENVIRONMENT.md).

Read rate-limit headers from the last response:

```ts
await client.countries.list();
const resp = client.lastResponse;
console.log(resp?.headers.get("X-RateLimit-Remaining"));
```

The same `lastResponse` is populated when a call fails, so you can
inspect `X-Request-Id` and rate-limit headers after an error too:

```ts
try {
  await client.laws.retrieve("es", "unknown");
} catch (err) {
  console.error(client.lastResponse?.headers.get("X-Request-Id"));
  throw err;
}
```

### Cleanup

The client holds no persistent connection pool (Node's `fetch` manages
sockets globally), but `close()` is exported for API symmetry across
SDKs. TS 5.2+ `await using` is supported:

```ts
{
  await using client = new Legalize({ apiKey: "leg_..." });
  await client.countries.list();
} // client auto-disposed
```

## Retries

Auto-retries on 429 + 5xx + transport errors, with exponential backoff
and full jitter. `Retry-After` (integer seconds or HTTP-date form) is
honored when present, capped at `maxDelay`.

**POST and PATCH are NOT retried by default** — they may be
non-idempotent. Opt in per-policy with `retryNonIdempotent: true`, or
send an `Idempotency-Key` and wrap your own retry loop.

## Errors

All errors inherit from `LegalizeError`. Catch the specific one you
care about and let the rest bubble:

```ts
import {
  AuthenticationError,     // 401 — bad/missing key
  ForbiddenError,          // 403
  NotFoundError,           // 404
  InvalidRequestError,     // 400
  ValidationError,         // 422
  RateLimitError,          // 429 — retried automatically by default
  ServerError,             // 5xx
  ServiceUnavailableError, // 503
  APIConnectionError,      // network failure
  APITimeoutError,         // timeout
  WebhookVerificationError,
} from "legalize";
```

Every `APIError` exposes `.statusCode`, `.code`, `.body`, `.response`,
and `.requestId`.

## Compatibility

- Node 20, 22, 24
- Linux, macOS, Windows
- ESM and CommonJS consumers (dual package)

## Links

- [API reference](https://legalize.dev/api/docs)
- [Monorepo](https://github.com/legalize-dev/legalize-sdks) (all language SDKs)
- [Changelog](https://github.com/legalize-dev/legalize-sdks/blob/main/node/CHANGELOG.md)
- [Contributing](https://github.com/legalize-dev/legalize-sdks/blob/main/CONTRIBUTING.md)

## License

MIT
