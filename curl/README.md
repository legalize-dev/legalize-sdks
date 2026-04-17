# curl quickstart

No SDK installation needed — the Legalize API is plain JSON over HTTPS.
Use these snippets as a starting point for shell scripts or anywhere an
SDK is too heavy.

## Setup

```bash
export LEGALIZE_API_KEY=leg_...
alias legalize='curl -sSf -H "Authorization: Bearer $LEGALIZE_API_KEY"'
```

## List countries

```bash
legalize https://legalize.dev/api/v1/countries | jq
```

## Search laws

```bash
legalize 'https://legalize.dev/api/v1/es/laws?q=protecci%C3%B3n+de+datos&per_page=5' | jq '.results[].title'
```

## Fetch a law with content

```bash
legalize https://legalize.dev/api/v1/es/laws/ley_organica_3_2018 | jq '.title, .content_md' | head
```

## Time-travel to a historical version

```bash
SHA=$(legalize https://legalize.dev/api/v1/es/laws/ley_organica_3_2018/commits | jq -r '.commits[-1].sha')
legalize "https://legalize.dev/api/v1/es/laws/ley_organica_3_2018/at/$SHA" | jq -r .content_md
```

## Verify a webhook (bash)

```bash
# Given: RAW_BODY, TIMESTAMP, SIG_HEADER, SECRET
SIGNED="${TIMESTAMP}.${RAW_BODY}"
EXPECTED="v1=$(printf '%s' "$SIGNED" | openssl dgst -sha256 -hmac "$SECRET" -r | cut -d' ' -f1)"
[ "$SIG_HEADER" = "$EXPECTED" ] && echo "OK" || echo "INVALID"
```

Replay-protection: also reject if ``$(date +%s) - $TIMESTAMP`` is greater
than 300 seconds.
