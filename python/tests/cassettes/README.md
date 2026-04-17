# VCR cassettes

Each cassette records one endpoint's live HTTP traffic. Cassettes are
replayed offline in CI — no network is used during normal test runs.

## Recording a cassette

```bash
# One-off: record against the real API.
LEGALIZE_API_KEY=leg_... VCR_RECORD=new pytest tests/vcr -k <test_name>
```

Modes (set ``VCR_RECORD``):

- ``none`` (default) — replay only; fail if a cassette is missing
- ``new_episodes`` — record new interactions, replay existing ones
- ``new`` — record only if the cassette does not exist yet
- ``all`` — overwrite existing cassettes (use sparingly)

## What we redact

- The ``Authorization`` header is replaced with ``Bearer leg_REDACTED``.
- The ``X-Request-Id`` response header is kept (useful for debugging).
- Nothing else — responses from the Legalize API are public data.

## When to re-record

- After a breaking API change (update cassette, open PR with both the
  code change and the cassette diff in the same commit).
- After a bug fix where the server now returns something different.
- Never "just because" — drift in cassettes vs. prod is the whole
  problem they exist to detect.
