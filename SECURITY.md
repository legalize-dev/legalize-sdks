# Security policy

## Reporting a vulnerability

If you believe you have found a security vulnerability in the Legalize
SDKs, please report it responsibly.

**Do not open a public GitHub issue.**

Instead, email **security@legalize.dev** with:

- A description of the issue
- Steps to reproduce
- The affected SDK and version
- Any proof-of-concept code, if applicable

We aim to acknowledge reports within 3 business days and ship a fix
within 30 days for confirmed vulnerabilities.

## Scope

In scope:

- All SDK code under `python/`, and future `node/`, `go/` directories
- The webhook signature verification utility (`legalize.webhooks`)
- Dependency supply-chain issues affecting SDK users

Out of scope:

- The Legalize API itself — report those at the web repo or the same email.
- Issues in third-party dependencies that have a pending upstream fix.

## Signed commits

Maintainer commits are GPG-signed. Community PRs are not required to
sign, but the merge commit will be signed.
