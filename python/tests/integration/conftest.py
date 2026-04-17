"""Integration test config — real requests against https://legalize.dev.

These tests are OPT-IN. They only run when ``LEGALIZE_API_KEY`` is set
in the environment. Without it, the whole directory is skipped at
collection time so the default ``pytest`` run stays offline.

Run the integration suite locally::

    LEGALIZE_API_KEY=leg_... pytest tests/integration -v

Run against a staging host::

    LEGALIZE_API_KEY=leg_... LEGALIZE_BASE_URL=https://staging.legalize.dev \\
        pytest tests/integration -v
"""

from __future__ import annotations

import os

import pytest

from legalize import AsyncLegalize, Legalize

_API_KEY = os.environ.get("LEGALIZE_API_KEY")
_BASE_URL = os.environ.get("LEGALIZE_BASE_URL", "https://legalize.dev")


if not _API_KEY:
    pytest.skip(
        "LEGALIZE_API_KEY not set — skipping live integration tests",
        allow_module_level=True,
    )


@pytest.fixture(scope="session")
def base_url() -> str:
    return _BASE_URL


@pytest.fixture(scope="session")
def api_key() -> str:
    assert _API_KEY is not None
    return _API_KEY


@pytest.fixture
def client(api_key: str, base_url: str) -> Legalize:
    c = Legalize(api_key=api_key, base_url=base_url, timeout=30.0)
    yield c
    c.close()


@pytest.fixture
async def aclient(api_key: str, base_url: str) -> AsyncLegalize:
    c = AsyncLegalize(api_key=api_key, base_url=base_url, timeout=30.0)
    yield c
    await c.aclose()
