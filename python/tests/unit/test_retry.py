"""Retry policy logic and client-side retry loop."""

from __future__ import annotations

from collections.abc import Callable
from unittest import mock

import httpx
import pytest

from legalize import APIError, APITimeoutError, Legalize, RateLimitError, RetryPolicy
from legalize._retry import RETRY_STATUSES, parse_retry_after


class TestParseRetryAfter:
    def test_seconds(self):
        assert parse_retry_after("30") == 30

    def test_zero(self):
        assert parse_retry_after("0") == 0

    def test_negative_clamped_to_zero(self):
        assert parse_retry_after("-5") == 0

    def test_none(self):
        assert parse_retry_after(None) is None

    def test_junk(self):
        assert parse_retry_after("later please") is None


class TestShouldRetry:
    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_retries_transient_statuses(self, status):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=status)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
    def test_does_not_retry_client_errors(self, status):
        p = RetryPolicy(max_retries=3)
        assert not p.should_retry(0, status=status)

    def test_retries_transport_errors(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=None)

    def test_stops_at_max_attempts(self):
        p = RetryPolicy(max_retries=2)
        assert p.should_retry(0, status=500)
        assert p.should_retry(1, status=500)
        assert not p.should_retry(2, status=500)

    def test_retry_statuses_constant(self):
        # Regression: make sure we don't accidentally widen the set.
        assert RETRY_STATUSES == frozenset({429, 500, 502, 503, 504})


class TestComputeDelay:
    def test_retry_after_wins(self):
        p = RetryPolicy(max_delay=60)
        assert p.compute_delay(0, retry_after=10) == 10

    def test_retry_after_capped(self):
        p = RetryPolicy(max_delay=5)
        assert p.compute_delay(0, retry_after=999) == 5

    def test_no_retry_after_uses_backoff(self, monkeypatch):
        p = RetryPolicy(initial_delay=1.0, backoff_factor=2.0, max_delay=100)
        monkeypatch.setattr("random.uniform", lambda _a, b: b)
        assert p.compute_delay(0, retry_after=None) == 1.0
        assert p.compute_delay(1, retry_after=None) == 2.0
        assert p.compute_delay(2, retry_after=None) == 4.0

    def test_backoff_capped_by_max_delay(self, monkeypatch):
        p = RetryPolicy(initial_delay=10.0, backoff_factor=10.0, max_delay=5)
        monkeypatch.setattr("random.uniform", lambda _a, b: b)
        assert p.compute_delay(5, retry_after=None) == 5

    def test_jitter_is_within_bounds(self):
        p = RetryPolicy(initial_delay=1.0, backoff_factor=2.0, max_delay=100)
        for attempt in range(5):
            for _ in range(50):
                delay = p.compute_delay(attempt, retry_after=None)
                assert 0 <= delay <= min(100, 1.0 * 2.0**attempt)


# ---- end-to-end retry behavior via MockTransport ----------------------


def _build_client(
    responses: list[httpx.Response], *, max_retries: int = 2
) -> tuple[Legalize, list[int]]:
    """Build a client that returns ``responses[i]`` for call i.

    Returns ``(client, call_counter)`` where ``call_counter[0]`` is the
    number of requests the SDK issued.
    """
    counter = [0]

    def handler(_req: httpx.Request) -> httpx.Response:
        idx = counter[0]
        counter[0] += 1
        return responses[idx]

    c = Legalize(
        api_key="leg_test",
        base_url="http://testserver",
        retry=RetryPolicy(max_retries=max_retries, initial_delay=0, max_delay=0),
        transport=httpx.MockTransport(handler),
    )
    return c, counter


class TestRetryIntegration:
    def test_retries_on_500_then_succeeds(self):
        responses = [
            httpx.Response(500, json={"detail": "err"}),
            httpx.Response(500, json={"detail": "err"}),
            httpx.Response(200, json=[]),
        ]
        c, calls = _build_client(responses, max_retries=3)
        with c:
            out = c.request("GET", "/api/v1/countries")
            assert out == []
            assert calls[0] == 3

    def test_gives_up_after_max_retries(self):
        responses = [httpx.Response(500, json={"detail": "nope"})] * 5
        c, calls = _build_client(responses, max_retries=2)
        with c, pytest.raises(APIError):
            c.request("GET", "/api/v1/countries")
        # max_retries=2 → 1 initial + 2 retries = 3 calls
        assert calls[0] == 3

    def test_does_not_retry_404(self):
        responses = [
            httpx.Response(404, json={"detail": "not found"}),
            httpx.Response(200, json=[]),
        ]
        c, calls = _build_client(responses, max_retries=3)
        with c, pytest.raises(APIError):
            c.request("GET", "/api/v1/countries")
        assert calls[0] == 1

    def test_429_respects_retry_after_from_body(self):
        responses = [
            httpx.Response(
                429,
                json={"detail": {"error": "rate", "message": "slow", "retry_after": 1}},
            ),
            httpx.Response(200, json=[]),
        ]
        c, calls = _build_client(responses, max_retries=3)
        slept: list[float] = []
        with mock.patch("time.sleep", side_effect=slept.append), c:
            c.request("GET", "/api/v1/countries")
        assert calls[0] == 2
        # Retry-After from header is what sleep sees, not the body. The
        # body field is only exposed on RateLimitError. Sleep uses the
        # header. Without a header, backoff is 0 (max_delay=0 in fixture).
        assert slept == [0]

    def test_429_respects_retry_after_header(self):
        # Use a real max_delay so retry_after isn't capped to 0 by the
        # test fixture. The SDK intentionally caps server-provided
        # retry_after at max_delay (matches Stripe/OpenAI behavior).
        responses = [
            httpx.Response(429, headers={"retry-after": "2"}, json={"detail": "too many"}),
            httpx.Response(200, json=[]),
        ]
        counter = [0]

        def handler(_req):
            idx = counter[0]
            counter[0] += 1
            return responses[idx]

        c = Legalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=3, initial_delay=0, max_delay=60),
            transport=httpx.MockTransport(handler),
        )
        slept: list[float] = []
        with mock.patch("time.sleep", side_effect=slept.append), c:
            c.request("GET", "/api/v1/countries")
        assert counter[0] == 2
        assert slept == [2]

    def test_server_retry_after_capped_at_max_delay(self):
        # Abuse protection: if server says "wait 10 hours" we don't.
        responses = [
            httpx.Response(429, headers={"retry-after": "36000"}),
            httpx.Response(200, json=[]),
        ]
        counter = [0]

        def handler(_req):
            idx = counter[0]
            counter[0] += 1
            return responses[idx]

        c = Legalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=3, initial_delay=0, max_delay=5),
            transport=httpx.MockTransport(handler),
        )
        slept: list[float] = []
        with mock.patch("time.sleep", side_effect=slept.append), c:
            c.request("GET", "/api/v1/countries")
        assert slept == [5]

    def test_transport_error_retries_then_raises(self):
        def handler(_req):
            raise httpx.ConnectTimeout("nope")

        c = Legalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=1, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        with (
            c,
            mock.patch("time.sleep"),
            pytest.raises(APITimeoutError),
        ):
            c.request("GET", "/api/v1/countries")

    def test_raised_error_is_rate_limit_with_retry_after(self):
        response = httpx.Response(
            429,
            json={"detail": {"error": "rate", "message": "slow", "retry_after": 42}},
        )
        c, _ = _build_client([response], max_retries=0)
        with c, pytest.raises(RateLimitError) as ei:
            c.request("GET", "/api/v1/countries")
        assert ei.value.retry_after == 42


# ---- no retries when max_retries=0 ------------------------------------


class TestZeroRetries:
    def test_no_retries_fires_once(self):
        responses = [httpx.Response(500, json={"detail": "boom"})]
        c, calls = _build_client(responses, max_retries=0)
        with c, pytest.raises(APIError):
            c.request("GET", "/api/v1/countries")
        assert calls[0] == 1


# Tell linters the fixture holder is used even when tests skip it
_: Callable[..., Legalize] | None = None
