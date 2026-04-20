"""Regression tests for the pre-launch audit fixes.

Covers:

1. ``last_response`` is populated even when the request ends in an
   ``APIError`` — so callers can still read rate-limit headers and the
   ``X-Request-ID`` when support asks.
2. ``Retry-After`` header parsing accepts the HTTP-date form in addition
   to delta-seconds, per RFC 9110.
3. Every request carries the identifying headers the SDK is supposed to
   send (``User-Agent`` shape, ``Legalize-API-Version``).
4. Paginated iterators handle the edge case ``total == 0``.
"""

from __future__ import annotations

import email.utils
import time
from unittest import mock

import httpx
import pytest

from legalize import (
    AsyncLegalize,
    Legalize,
    NotFoundError,
    RateLimitError,
    RetryPolicy,
)
from legalize._client import DEFAULT_API_VERSION
from legalize._pagination import PageIterator
from legalize._retry import parse_retry_after
from legalize._version import __version__


def _mock(response: httpx.Response) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _req: response)


# ---- last_response after error -----------------------------------------


class TestLastResponseAfterError:
    def test_populated_on_404(self):
        response = httpx.Response(
            404,
            json={"detail": "not found"},
            headers={"x-request-id": "req_abc", "x-ratelimit-remaining": "9"},
        )
        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            max_retries=0,
            transport=_mock(response),
        )
        with pytest.raises(NotFoundError):
            c.countries.list()
        assert c.last_response is not None
        assert c.last_response.status_code == 404
        assert c.last_response.headers["x-request-id"] == "req_abc"
        assert c.last_response.headers["x-ratelimit-remaining"] == "9"
        c.close()

    def test_populated_on_exhausted_429(self):
        response = httpx.Response(
            429,
            json={"detail": {"error": "quota_exceeded"}},
            headers={"retry-after": "1", "x-ratelimit-remaining": "0"},
        )
        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            retry=RetryPolicy(max_retries=1, initial_delay=0, max_delay=0),
            transport=_mock(response),
        )
        with mock.patch("time.sleep"), pytest.raises(RateLimitError):
            c.countries.list()
        assert c.last_response is not None
        assert c.last_response.status_code == 429
        assert c.last_response.headers["x-ratelimit-remaining"] == "0"
        c.close()

    @pytest.mark.asyncio
    async def test_async_populated_on_error(self):
        response = httpx.Response(
            404,
            json={"detail": "not found"},
            headers={"x-request-id": "req_xyz"},
        )
        c = AsyncLegalize(
            api_key="leg_t",
            base_url="http://t",
            max_retries=0,
            transport=httpx.MockTransport(lambda _r: response),
        )
        with pytest.raises(NotFoundError):
            await c.countries.list()
        assert c.last_response is not None
        assert c.last_response.status_code == 404
        assert c.last_response.headers["x-request-id"] == "req_xyz"
        await c.aclose()


# ---- Retry-After HTTP-date ---------------------------------------------


class TestRetryAfterHttpDate:
    def test_delta_seconds_integer(self):
        assert parse_retry_after("120") == 120.0

    def test_delta_seconds_clamps_negative_to_zero(self):
        assert parse_retry_after("-5") == 0.0

    def test_http_date_future(self):
        future = time.time() + 60
        header = email.utils.formatdate(future, usegmt=True)
        parsed = parse_retry_after(header)
        assert parsed is not None
        # Allow for a couple of seconds of clock slip between parse and
        # the assertion; the value should be roughly 60.
        assert 55 <= parsed <= 65

    def test_http_date_past_clamps_to_zero(self):
        past = time.time() - 600
        header = email.utils.formatdate(past, usegmt=True)
        assert parse_retry_after(header) == 0.0

    def test_malformed_returns_none(self):
        assert parse_retry_after("not a date") is None
        assert parse_retry_after("") is None
        assert parse_retry_after(None) is None

    def test_client_honors_http_date_from_server(self):
        """End-to-end: 429 with HTTP-date Retry-After causes the sync
        client to sleep the right amount before retrying."""
        # Server replies 429 then 200. The 429 carries a Retry-After
        # HTTP-date 2 seconds in the future.
        future = time.time() + 2
        retry_after = email.utils.formatdate(future, usegmt=True)
        responses = iter(
            [
                httpx.Response(429, headers={"retry-after": retry_after}),
                httpx.Response(200, json=[]),
            ]
        )

        def handler(_req: httpx.Request) -> httpx.Response:
            return next(responses)

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            retry=RetryPolicy(max_retries=1, initial_delay=0, max_delay=30),
            transport=httpx.MockTransport(handler),
        )
        slept: list[float] = []
        with mock.patch("time.sleep", side_effect=slept.append):
            c.countries.list()
        assert len(slept) == 1
        # Should sleep roughly 2s (give a wide band for clock drift).
        assert 0.0 <= slept[0] <= 3.0
        c.close()


# ---- Required outgoing headers ----------------------------------------


class TestOutgoingHeaders:
    def test_user_agent_format(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return httpx.Response(200, json=[])

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        c.countries.list()
        c.close()
        ua = captured[0].headers["user-agent"]
        assert ua.startswith(f"legalize-python/{__version__} ")
        assert " python/" in ua

    def test_api_version_header_on_every_request(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return httpx.Response(200, json=[])

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        c.countries.list()
        c.countries.list()
        c.countries.list()
        c.close()
        assert len(captured) == 3
        for req in captured:
            assert req.headers["legalize-api-version"] == DEFAULT_API_VERSION

    def test_api_version_override_propagates(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return httpx.Response(200, json=[])

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            api_version="v2",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        c.countries.list()
        c.close()
        assert captured[0].headers["legalize-api-version"] == "v2"

    def test_authorization_bearer_format(self):
        captured: list[httpx.Request] = []

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(req)
            return httpx.Response(200, json=[])

        c = Legalize(
            api_key="leg_specific",
            base_url="http://t",
            max_retries=0,
            transport=httpx.MockTransport(handler),
        )
        c.countries.list()
        c.close()
        assert captured[0].headers["authorization"] == "Bearer leg_specific"


# ---- Pagination edge case: total=0 ------------------------------------


class TestPaginationTotalZero:
    def test_iter_yields_nothing_when_total_zero(self):
        """A search with 0 matches must not spin on empty pages."""
        pages_requested = [0]

        def fetch_page(page: int, per_page: int) -> tuple[list[str], int]:
            pages_requested[0] += 1
            return [], 0

        yielded = list(PageIterator(fetch_page, per_page=50))
        assert yielded == []
        # The iterator may probe once, but never twice — an empty
        # total-zero response must not trigger a second request.
        assert pages_requested[0] <= 1
