"""Shared pytest fixtures.

Tests use ``httpx.MockTransport`` so the sync/async clients never touch
the network. The ``mock_transport`` fixture accepts a handler callable
that receives an ``httpx.Request`` and must return an ``httpx.Response``.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from legalize import AsyncLegalize, Legalize, RetryPolicy

API_KEY = "leg_test_1234567890"


Handler = Callable[[httpx.Request], httpx.Response]


def _make_transport(handler: Handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.fixture
def handler() -> list[Handler]:
    """Mutable holder for the active handler used by ``client``/``aclient``.

    Tests replace ``handler[0]`` with their own callable.
    """
    return [lambda request: httpx.Response(500, json={"detail": "no handler set"})]


@pytest.fixture
def client(handler: list[Handler]) -> Legalize:
    def dispatch(request: httpx.Request) -> httpx.Response:
        return handler[0](request)

    # max_retries=0 in most unit tests so we can assert on the exact
    # number of calls the SDK made. Tests that exercise retries build
    # their own client with the retry policy they want.
    c = Legalize(
        api_key=API_KEY,
        base_url="http://testserver",
        max_retries=0,
        transport=_make_transport(dispatch),
    )
    yield c
    c.close()


@pytest.fixture
def aclient(handler: list[Handler]) -> AsyncLegalize:
    async def dispatch(request: httpx.Request) -> httpx.Response:
        return handler[0](request)

    c = AsyncLegalize(
        api_key=API_KEY,
        base_url="http://testserver",
        max_retries=0,
        transport=httpx.MockTransport(dispatch),
    )
    return c


@pytest.fixture
def retry_client_factory() -> Callable[..., Legalize]:
    """Factory that lets a test pick its own retry policy + handler."""

    def _make(handler: Handler, *, policy: RetryPolicy | None = None) -> Legalize:
        return Legalize(
            api_key=API_KEY,
            base_url="http://testserver",
            retry=policy or RetryPolicy(max_retries=2, initial_delay=0, max_delay=0),
            transport=_make_transport(handler),
        )

    return _make


# ---- fixtures shared with webhook tests --------------------------------

SECRET = "whsec_unit_test_secret_with_some_length"


@pytest.fixture
def webhook_secret() -> str:
    return SECRET
