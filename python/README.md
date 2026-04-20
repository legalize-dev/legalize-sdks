# legalize

[![python-ci](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml/badge.svg)](https://github.com/legalize-dev/legalize-sdks/actions/workflows/python-ci.yml)
[![PyPI](https://img.shields.io/pypi/v/legalize.svg)](https://pypi.org/project/legalize/)
[![Python versions](https://img.shields.io/pypi/pyversions/legalize.svg)](https://pypi.org/project/legalize/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/legalize-dev/legalize-sdks/blob/main/LICENSE)

Official Python client for the [Legalize API](https://legalize.dev/api) — legal texts as structured, versioned data.

```bash
pip install legalize
```

```python
from legalize import Legalize

client = Legalize(api_key="leg_...")

for law in client.laws.iter(country="es", law_type="ley_organica"):
    print(law.id, law.title)
```

## Why this SDK

- **Typed end-to-end.** Pydantic v2 models generated from the canonical
  OpenAPI spec. `py.typed` ships in the wheel. `mypy --strict` clean.
- **Sync by default, async when you need it.** `Legalize` and
  `AsyncLegalize` expose the same resource API and error types — swap
  one for the other without rewriting your call sites.
- **Retries with backoff built in.** Honors `Retry-After`, handles
  429/5xx, exponential delay with jitter, all configurable.
- **Webhook verification is a one-liner.** Constant-time HMAC compare,
  5-minute anti-replay window, clock-skew tolerant.
- **No magic, no frameworks.** One client, one method per endpoint.

## Quick tour

### List, iterate, search

```python
# One page
page = client.laws.list(country="es", page=1, per_page=50)
print(page.total, len(page.items))

# Auto-paginated iterator (fetches pages as needed)
for law in client.laws.iter(country="es", status="vigente"):
    ...

# Full-text search
results = client.laws.search(country="es", q="protección de datos")
```

### Time-travel

Every law has a git-tracked history. Retrieve it at any past revision:

```python
commits = client.laws.commits(country="es", law_id="ley_organica_3_2018")
past = client.laws.at_commit(
    country="es",
    law_id="ley_organica_3_2018",
    sha=commits.items[-1].sha,
)
print(past.content)  # Markdown at that revision
```

### Async

```python
import asyncio
from legalize import AsyncLegalize

async def main():
    async with AsyncLegalize(api_key="leg_...") as client:
        page = await client.laws.list(country="es")
        async for law in client.laws.iter(country="fr"):
            print(law.id)

asyncio.run(main())
```

### Webhooks

Verify a signed delivery in one call:

```python
from legalize import Webhook, WebhookVerificationError

try:
    event = Webhook.verify(
        payload=request.body,                              # raw bytes
        sig_header=request.headers["X-Legalize-Signature"],
        timestamp=request.headers["X-Legalize-Timestamp"],
        secret=os.environ["LEGALIZE_WHSEC"],
    )
except WebhookVerificationError:
    return Response(status_code=400)

if event.type == "law.updated":
    ...
```

Working Flask and FastAPI receivers in
[`examples/`](https://github.com/legalize-dev/legalize-sdks/tree/main/python/examples).

## Configuration

```python
from legalize import Legalize, RetryPolicy

client = Legalize(
    api_key="leg_...",             # or env: LEGALIZE_API_KEY
    base_url="https://legalize.dev",
    api_version="v1",              # negotiated via Legalize-API-Version
    timeout=30.0,
    retry=RetryPolicy(max_retries=5, initial_delay=0.5, max_delay=10.0),
    default_headers={"X-Correlation-Id": "..."},
)
```

Read rate-limit headers from the last response:

```python
client.countries.list()
resp = client.last_response
print(resp.headers.get("X-RateLimit-Remaining"))
```

## Errors

All errors inherit from `LegalizeError`. Catch the specific one you care
about and let the rest bubble:

```python
from legalize import (
    AuthenticationError,   # 401 — bad/missing key
    ForbiddenError,        # 403
    NotFoundError,         # 404
    InvalidRequestError,   # 400
    ValidationError,       # 422
    RateLimitError,        # 429 — retried automatically by default
    ServerError,           # 5xx
    APIConnectionError,    # network failure
    APITimeoutError,       # timeout
    WebhookVerificationError,
)
```

Every `APIError` exposes `.status_code`, `.code`, `.body`, and
`.response` for debugging.

## Compatibility

- Python 3.10, 3.11, 3.12, 3.13
- Linux, macOS, Windows
- `httpx` ≥ 0.27, `pydantic` ≥ 2.6

## Links

- [API reference](https://legalize.dev/api/docs)
- [Monorepo](https://github.com/legalize-dev/legalize-sdks) (sources for all language SDKs)
- [Changelog](https://github.com/legalize-dev/legalize-sdks/blob/main/python/CHANGELOG.md)
- [Contributing](https://github.com/legalize-dev/legalize-sdks/blob/main/CONTRIBUTING.md)

## License

MIT
