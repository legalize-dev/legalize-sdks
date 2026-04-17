"""Aggregate stats for a country (reform activity, most-reformed laws)."""

from __future__ import annotations

import os
import sys

from legalize import Legalize


def main() -> int:
    country = sys.argv[1] if len(sys.argv) > 1 else "es"

    with Legalize(api_key=os.environ["LEGALIZE_API_KEY"]) as client:
        stats = client.stats.retrieve(country=country)

    print(f"Law types in {country}: {', '.join(stats.law_types)}\n")

    if stats.reform_activity_by_year:
        print("Reforms per year (last 10):")
        for row in stats.reform_activity_by_year[-10:]:
            print(f"  {row['year']}  {row['count']:>6}")

    print("\nTop 5 most-reformed laws:")
    for row in stats.most_reformed_laws[:5]:
        print(f"  {row['id']}  {row['title'][:60]}  ({row['count']} reforms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
