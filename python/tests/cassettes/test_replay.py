"""Replay cassettes of real API responses.

Each test here will skip if its cassette has not been recorded yet
(the default VCR mode is ``none`` — replay-only). To record::

    LEGALIZE_API_KEY=leg_... VCR_RECORD=new pytest tests/vcr

The cassettes directory is committed to the repo; recording is a human
decision (it updates the ground truth for what the server is returning).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from legalize import Legalize

CASSETTES = Path(__file__).parent / "cassettes"


def _cassette_exists(name: str) -> bool:
    return (CASSETTES / name).exists()


def _client() -> Legalize:
    # Real key only needed in record mode. Replay mode ignores auth.
    key = os.environ.get("LEGALIZE_API_KEY", "leg_cassette_replay_key")
    return Legalize(api_key=key, max_retries=0)


@pytest.mark.vcr
def test_countries_list(vcr_cassette):
    if not _cassette_exists(vcr_cassette) and os.environ.get("VCR_RECORD", "none") == "none":
        pytest.skip(f"cassette {vcr_cassette} not recorded")
    c = _client()
    try:
        out = c.countries.list()
        assert len(out) > 0
        codes = {x.country for x in out}
        # Sanity checks that should hold for the foreseeable future.
        assert "es" in codes
    finally:
        c.close()


@pytest.mark.vcr
def test_spain_stats(vcr_cassette):
    if not _cassette_exists(vcr_cassette) and os.environ.get("VCR_RECORD", "none") == "none":
        pytest.skip(f"cassette {vcr_cassette} not recorded")
    c = _client()
    try:
        stats = c.stats.retrieve("es")
        assert stats.country == "es"
        assert len(stats.law_types) > 0
    finally:
        c.close()


@pytest.mark.vcr
def test_spain_first_page_of_laws(vcr_cassette):
    if not _cassette_exists(vcr_cassette) and os.environ.get("VCR_RECORD", "none") == "none":
        pytest.skip(f"cassette {vcr_cassette} not recorded")
    c = _client()
    try:
        page = c.laws.list("es", page=1, per_page=5)
        assert page.country == "es"
        assert len(page.results) <= 5
    finally:
        c.close()
