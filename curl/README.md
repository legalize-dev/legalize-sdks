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

## Request XML instead of JSON

Every endpoint also speaks XML via content negotiation. Send
`Accept: application/xml`, or append `?format=xml` (handy when you can't
set a header):

```bash
# Accept header
legalize -H "Accept: application/xml" \
  https://legalize.dev/api/v1/es/laws/ley_organica_3_2018

# Query param — no extra header needed
legalize 'https://legalize.dev/api/v1/es/laws/ley_organica_3_2018?format=xml'
```

JSON stays the default, so every snippet above without the header is
unchanged. Errors honor the same negotiation: an XML request gets an XML
error envelope.

## Time-travel to a historical version

```bash
SHA=$(legalize https://legalize.dev/api/v1/es/laws/ley_organica_3_2018/commits | jq -r '.commits[-1].sha')
legalize "https://legalize.dev/api/v1/es/laws/ley_organica_3_2018/at/$SHA" | jq -r .content_md

# Or by date — the server resolves it to a version and tells you which one.
legalize "https://legalize.dev/api/v1/es/laws/ley_organica_3_2018/at?date=2019-05-13" \
  | jq '{sha, version_date}'
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
