"""Parallel fetches with the async client.

Kicks off ``stats`` and ``countries`` concurrently. Scales to fetching
per-country details in parallel for dashboards.

Usage::

    LEGALIZE_API_KEY=leg_... python examples/async_client.py
"""

from __future__ import annotations

import asyncio
import os

from legalize import AsyncLegalize


async def main() -> None:
    async with AsyncLegalize(api_key=os.environ["LEGALIZE_API_KEY"]) as client:
        countries, spain_stats = await asyncio.gather(
            client.countries.list(),
            client.stats.retrieve("es"),
        )

    print(f"Serving {len(countries)} countries: {', '.join(c.country for c in countries)}")
    print(f"Spain has {len(spain_stats.law_types)} law types.")


if __name__ == "__main__":
    asyncio.run(main())
