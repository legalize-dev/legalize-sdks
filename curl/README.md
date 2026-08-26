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

## Tell a quotable text from a stale one

Portugal serves 166,422 of its 171,739 acts **as published**: the body is the
original and every amendment since is a separate act. A law can be in force and
its text still be out of date, so `status` does not answer "can I quote this?".
`text_superseded` does:

```bash
legalize https://legalize.dev/api/v1/pt/laws/DRE-1984-394-B-605547/meta \
  | jq '{title, status, text_state, reform_count, text_superseded}'
```

```json
{
  "title": "Decreto-Lei n.º 394-B/84 — Aprova o Código do Imposto sobre o Valor Acrescentado (IVA)",
  "status": "in_force",
  "text_state": "as_enacted",
  "reform_count": 158,
  "text_superseded": true
}
```

In force, and not the law in force. `text_state` says what the body is:
`point_in_time` (the law as it stood on its date), `current` (the latest text
the source publishes) or `as_enacted` (the act as published). `text_superseded`
is `true` when that body is out of date.

**Do not compute it yourself from `reform_count`.** Where a source publishes the
same act twice — Portugal does for 338 of them — the amendments are recorded
against the consolidated copy, and the as-published one shows `reform_count: 0`
while being provably stale. 227 of Portugal's laws are exactly that. The server
resolves it; the field is the answer.

Filter on the state server-side rather than pulling the corpus and sorting at
home:

```bash
# Only consolidated text — 5,317 of Portugal's laws
legalize 'https://legalize.dev/api/v1/pt/laws?text_state=point_in_time&per_page=1' | jq .total

# Only the acts as published — 166,422
legalize 'https://legalize.dev/api/v1/pt/laws?text_state=as_enacted&per_page=1' | jq .total
```

Omit `text_state` and you get every state, which is what this endpoint has
always returned.

## See which act made each change

Each reform names the amending act, so finding out what it was no longer costs
a call per row:

```bash
legalize 'https://legalize.dev/api/v1/pt/laws/DRE-1984-394-B-605547/reforms?limit=4' \
  | jq '.reforms[] | {date, source_id, source_title}'
```

```json
{"date": "2026-07-16", "source_id": "DRE-2026-298-1148213729", "source_title": "Portaria n.º 298/2026/1 — Alteração da Portaria n.º 221/2017, de 21 de julho, que aprova os modelos da declaração periódica do IVA, do anexo R e…"}
{"date": "2026-05-20", "source_id": "DRE-2026-97-1124493227", "source_title": null}
{"date": "2025-12-30", "source_id": "DRE-2025-73-A-993270096", "source_title": "Lei n.º 73-A/2025 — Orçamento do Estado para 2026"}
```

`source_title` is `null` when the amending act is not one we serve. How often
that happens depends on which text you are reading the history of, and the two
cases are nothing alike:

| history of a… | reforms | named | |
|---|---:|---:|---|
| `as_enacted` text | 120,687 | 119,915 | **99.4%** |
| `point_in_time` text | 9,942 | 0 | **0%** |

A consolidated text's amendments are recorded under the source's own revision
identifiers (`DRE-177088811@2022-01-09`), which are not law identifiers and
never resolve. Read that history for the dates; read the as-published act's
history to learn which acts changed it.

## Verify a webhook (bash)

```bash
# Given: RAW_BODY, TIMESTAMP, SIG_HEADER, SECRET
SIGNED="${TIMESTAMP}.${RAW_BODY}"
EXPECTED="v1=$(printf '%s' "$SIGNED" | openssl dgst -sha256 -hmac "$SECRET" -r | cut -d' ' -f1)"
[ "$SIG_HEADER" = "$EXPECTED" ] && echo "OK" || echo "INVALID"
```

Replay-protection: also reject if ``$(date +%s) - $TIMESTAMP`` is greater
than 300 seconds.
