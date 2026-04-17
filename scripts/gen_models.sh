#!/usr/bin/env bash
# Regenerate Python Pydantic models from the filtered OpenAPI spec.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$HERE/.."

"$HERE/fetch_openapi.sh"
python3 "$HERE/filter_openapi.py"

# Prefer the python SDK's venv if present, otherwise fall back to PATH.
CODEGEN="datamodel-codegen"
if [ -x "$ROOT/python/.venv/bin/datamodel-codegen" ]; then
  CODEGEN="$ROOT/python/.venv/bin/datamodel-codegen"
fi

OUT="$ROOT/python/src/legalize/models/_generated.py"

"$CODEGEN" \
  --input "$ROOT/openapi-sdk.json" \
  --input-file-type openapi \
  --output "$OUT" \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.10 \
  --use-standard-collections \
  --use-union-operator \
  --use-schema-description \
  --field-constraints \
  --disable-timestamp \
  --enum-field-as-literal all \
  --use-title-as-name \
  --collapse-root-models \
  --strict-nullable

echo "Wrote $OUT"
