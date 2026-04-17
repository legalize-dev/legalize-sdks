"""Full-text search across a country's laws.

Usage::

    LEGALIZE_API_KEY=leg_... python examples/search.py es "protección de datos"
"""

from __future__ import annotations

import os
import sys

from legalize import Legalize


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: search.py <country> <query>", file=sys.stderr)
        return 2
    country, query = sys.argv[1], sys.argv[2]

    with Legalize(api_key=os.environ["LEGALIZE_API_KEY"]) as client:
        page = client.laws.search(country=country, q=query, per_page=20)
        print(f"{page.total} matches for {query!r} in {country}\n")
        for law in page.results:
            print(f"  {law.id}  {law.title[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
