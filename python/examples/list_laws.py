"""List all laws for a country, auto-paginated.

Usage::

    LEGALIZE_API_KEY=leg_... python examples/list_laws.py es ley_organica
"""

from __future__ import annotations

import os
import sys

from legalize import Legalize


def main() -> int:
    country = sys.argv[1] if len(sys.argv) > 1 else "es"
    law_type = sys.argv[2] if len(sys.argv) > 2 else None

    with Legalize(api_key=os.environ["LEGALIZE_API_KEY"]) as client:
        for i, law in enumerate(client.laws.iter(country=country, law_type=law_type), start=1):
            print(f"{i:5}  {law.id}  {law.title[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
