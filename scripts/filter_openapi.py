#!/usr/bin/env python3
"""Filter the raw OpenAPI spec to only SDK-relevant endpoints.

Defensive: even if the server ships with include_in_schema=False for all
internal routes, this script strips anything that leaks. Outputs a
minimal spec used by the model code generator.

Kept SDK surface:
  - All /api/v1/* paths (tags: api, webhooks)
  - /api/health (tag: health)

Everything else is dropped: dashboard/admin/billing/site/sitemaps/etc.

Also drops schemas that are only referenced by dropped paths, so the
generated models directory stays clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SDK_PATH_PREFIXES = ("/api/v1/", "/api/health")
SDK_TAGS = {"api", "webhooks", "health"}


def keep_path(path: str) -> bool:
    return any(path == p or path.startswith(p) for p in SDK_PATH_PREFIXES)


def collect_schema_refs(obj: Any, acc: set[str]) -> None:
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            acc.add(ref.rsplit("/", 1)[-1])
        for v in obj.values():
            collect_schema_refs(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            collect_schema_refs(v, acc)


def transitively_close(
    seeds: set[str], schemas: dict[str, Any]
) -> set[str]:
    """Expand the seed set to include every schema reachable from it."""
    out = set(seeds)
    frontier = set(seeds)
    while frontier:
        nxt: set[str] = set()
        for name in frontier:
            if name not in schemas:
                continue
            collect_schema_refs(schemas[name], nxt)
        nxt -= out
        out |= nxt
        frontier = nxt
    return out


def filter_spec(spec: dict[str, Any]) -> dict[str, Any]:
    paths = spec.get("paths", {})
    kept_paths = {p: v for p, v in paths.items() if keep_path(p)}

    # Determine which schemas are reachable from kept paths.
    seeds: set[str] = set()
    collect_schema_refs(kept_paths, seeds)
    schemas = spec.get("components", {}).get("schemas", {})
    reachable = transitively_close(seeds, schemas)

    out = dict(spec)
    out["paths"] = kept_paths
    if "components" in out:
        components = dict(out["components"])
        components["schemas"] = {
            name: body for name, body in schemas.items() if name in reachable
        }
        out["components"] = components

    # Drop security schemes we don't use in the SDK surface, keep bearer.
    sec = out.get("components", {}).get("securitySchemes", {})
    if sec:
        out["components"]["securitySchemes"] = {
            k: v for k, v in sec.items() if v.get("type") in ("http", "apiKey")
        }

    return out


def main() -> int:
    src = ROOT / "openapi.json"
    dst = ROOT / "openapi-sdk.json"
    if not src.exists():
        print(f"missing {src}, run scripts/fetch_openapi.sh first", file=sys.stderr)
        return 1

    spec = json.loads(src.read_text())
    filtered = filter_spec(spec)

    dst.write_text(json.dumps(filtered, indent=2, sort_keys=True) + "\n")

    n_paths_in = len(spec.get("paths", {}))
    n_paths_out = len(filtered.get("paths", {}))
    n_schemas_in = len(spec.get("components", {}).get("schemas", {}))
    n_schemas_out = len(filtered.get("components", {}).get("schemas", {}))

    print(f"paths:   {n_paths_in} -> {n_paths_out}")
    print(f"schemas: {n_schemas_in} -> {n_schemas_out}")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
