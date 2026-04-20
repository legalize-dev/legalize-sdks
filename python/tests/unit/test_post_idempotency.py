"""Regression: POST and PATCH must not be auto-retried on 429/5xx.

Blindly retrying a non-idempotent request can duplicate server-side
effects — e.g. two webhook endpoints from one ``webhooks.create`` call,
two delivery retries from one ``webhooks.retry`` call. The SDK contract
(PARITY.md §5) allows automatic retries only for idempotent methods
by default. Callers that know a specific POST is safe to retry can
opt in per-policy with ``RetryPolicy(retry_non_idempotent=True)``.
"""

from __future__ import annotations

import httpx
import pytest

from legalize import APIError, Legalize, RetryPolicy
from legalize._retry import IDEMPOTENT_METHODS


class TestIdempotentMethodsConstant:
    def test_expected_set(self):
        assert IDEMPOTENT_METHODS == frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


class TestPolicyShouldRetry:
    def test_get_retries_on_500(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=500, method="GET") is True

    def test_post_does_not_retry_on_500(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=500, method="POST") is False

    def test_patch_does_not_retry_on_429(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=429, method="PATCH") is False

    def test_post_does_not_retry_on_transport_error(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=None, method="POST") is False

    def test_opt_in_allows_post_retry(self):
        p = RetryPolicy(max_retries=3, retry_non_idempotent=True)
        assert p.should_retry(0, status=500, method="POST") is True

    def test_case_insensitive_method(self):
        p = RetryPolicy(max_retries=3)
        assert p.should_retry(0, status=500, method="post") is False
        assert p.should_retry(0, status=500, method="put") is True


class TestClientEndToEnd:
    def test_post_not_retried_on_500(self):
        """A POST returning 500 is raised on the first attempt."""
        call_count = [0]

        def handler(_req: httpx.Request) -> httpx.Response:
            call_count[0] += 1
            return httpx.Response(500, json={"detail": "boom"})

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            retry=RetryPolicy(max_retries=3, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(APIError):
            c.request("POST", "/api/v1/webhooks", json={"url": "https://x"})
        assert call_count[0] == 1, f"POST retried {call_count[0]} times"
        c.close()

    def test_get_is_retried_on_500(self):
        """A GET returning 500 triggers retries per policy."""
        call_count = [0]

        def handler(_req: httpx.Request) -> httpx.Response:
            call_count[0] += 1
            return httpx.Response(500, json={"detail": "boom"})

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            retry=RetryPolicy(max_retries=2, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        import unittest.mock as mock

        with mock.patch("time.sleep"), pytest.raises(APIError):
            c.request("GET", "/api/v1/countries")
        # 1 initial + 2 retries
        assert call_count[0] == 3, f"GET called {call_count[0]} times, expected 3"
        c.close()

    def test_patch_not_retried_on_429(self):
        call_count = [0]

        def handler(_req: httpx.Request) -> httpx.Response:
            call_count[0] += 1
            return httpx.Response(429, headers={"retry-after": "1"})

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            retry=RetryPolicy(max_retries=3, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(APIError):
            c.request("PATCH", "/api/v1/webhooks/1", json={"url": "https://x"})
        assert call_count[0] == 1
        c.close()

    def test_post_retried_when_opt_in(self):
        call_count = [0]

        def handler(_req: httpx.Request) -> httpx.Response:
            call_count[0] += 1
            if call_count[0] < 3:
                return httpx.Response(500, json={"detail": "transient"})
            return httpx.Response(200, json={"id": 1})

        c = Legalize(
            api_key="leg_t",
            base_url="http://t",
            retry=RetryPolicy(
                max_retries=3, initial_delay=0, max_delay=0, retry_non_idempotent=True
            ),
            transport=httpx.MockTransport(handler),
        )
        import unittest.mock as mock

        with mock.patch("time.sleep"):
            result = c.request("POST", "/api/v1/webhooks", json={"url": "https://x"})
        assert result == {"id": 1}
        assert call_count[0] == 3
        c.close()
