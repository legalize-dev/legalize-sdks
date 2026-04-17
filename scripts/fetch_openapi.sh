#!/usr/bin/env bash
# Fetch the canonical OpenAPI spec from production.
set -euo pipefail

SPEC_URL="${LEGALIZE_SPEC_URL:-https://legalize.dev/openapi.json}"
OUT="$(dirname "$0")/../openapi.json"

curl -fsSL "$SPEC_URL" -o "$OUT"
echo "Wrote $(wc -c < "$OUT") bytes to $OUT"
