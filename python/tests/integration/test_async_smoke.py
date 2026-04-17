"""Async client smoke test against prod — confirms parity with sync."""

from __future__ import annotations

import asyncio

import pytest

from legalize import AsyncLegalize
from legalize.models import CountryInfo, StatsResponse

pytestmark = pytest.mark.asyncio


async def test_countries(aclient: AsyncLegalize):
    out = await aclient.countries.list()
    assert len(out) > 0
    assert all(isinstance(c, CountryInfo) for c in out)


async def test_stats(aclient: AsyncLegalize):
    stats = await aclient.stats.retrieve("es")
    assert isinstance(stats, StatsResponse)
    assert stats.country == "es"


async def test_parallel_fan_out(aclient: AsyncLegalize):
    """The whole point of async: multiple requests in parallel."""
    countries_task = aclient.countries.list()
    stats_task = aclient.stats.retrieve("es")
    law_types_task = aclient.law_types.list("es")

    countries, stats, law_types = await asyncio.gather(countries_task, stats_task, law_types_task)

    assert len(countries) > 0
    assert stats.country == "es"
    assert len(law_types) > 0


async def test_async_iter_laws(aclient: AsyncLegalize):
    collected = []
    async for law in aclient.laws.iter("es", per_page=50, limit=25):
        collected.append(law)
    assert len(collected) == 25
    assert len({law.id for law in collected}) == 25
