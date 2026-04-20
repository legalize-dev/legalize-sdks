"""Property-based tests for the retry machinery.

Hypothesis generates random sequences of server responses and random
retry policies, and we assert invariants that must hold regardless of
inputs:

1. The SDK never makes more than ``max_retries + 1`` requests.
2. The SDK never sleeps more than ``max_delay`` per individual retry.
3. The SDK never retries a non-retryable status code.
4. Given any Retry-After value in [0, max_delay], the SDK sleeps that
   exact amount (server instructions are authoritative within bounds).
"""

from __future__ import annotations

import contextlib
from unittest import mock

import httpx
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from legalize import APIError, Legalize, RetryPolicy
from legalize._retry import RETRY_STATUSES

NON_RETRY_STATUSES = [400, 401, 403, 404, 409, 422]


def _build_client(
    response_sequence: list[tuple[int, dict | None]],
    *,
    policy: RetryPolicy,
) -> tuple[Legalize, list[int]]:
    counter = [0]

    def handler(_req):
        idx = min(counter[0], len(response_sequence) - 1)
        status, headers = response_sequence[idx]
        counter[0] += 1
        return httpx.Response(status, headers=headers or {}, json={"detail": "x"})

    c = Legalize(
        api_key="leg_test",
        base_url="http://testserver",
        retry=policy,
        transport=httpx.MockTransport(handler),
    )
    return c, counter


@given(
    max_retries=st.integers(min_value=0, max_value=5),
    statuses=st.lists(
        st.sampled_from([*sorted(RETRY_STATUSES), 200]),
        min_size=1,
        max_size=8,
    ),
)
@settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_call_count_bounded(max_retries, statuses):
    policy = RetryPolicy(max_retries=max_retries, initial_delay=0, max_delay=0)
    seq = [(s, None) for s in statuses]
    c, counter = _build_client(seq, policy=policy)
    with c, mock.patch("time.sleep"), contextlib.suppress(APIError):
        c.request("GET", "/api/v1/countries")
    assert counter[0] <= max_retries + 1


@given(
    status=st.sampled_from(NON_RETRY_STATUSES),
    max_retries=st.integers(min_value=0, max_value=5),
)
@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_never_retries_non_retryable(status, max_retries):
    policy = RetryPolicy(max_retries=max_retries, initial_delay=0, max_delay=0)
    seq = [(status, None)] * 10
    c, counter = _build_client(seq, policy=policy)
    with c, mock.patch("time.sleep"), pytest.raises(APIError):
        c.request("GET", "/api/v1/countries")
    assert counter[0] == 1  # exactly one call, zero retries


@given(
    retry_after=st.integers(min_value=0, max_value=10),
    max_delay=st.integers(min_value=10, max_value=60),
)
@settings(
    max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
def test_retry_after_exact_sleep(retry_after, max_delay):
    # Server says wait N seconds, N < max_delay → sleep exactly N.
    policy = RetryPolicy(max_retries=1, initial_delay=0, max_delay=max_delay)
    seq = [
        (429, {"retry-after": str(retry_after)}),
        (200, None),
    ]
    c, counter = _build_client(seq, policy=policy)
    slept: list[float] = []
    with c, mock.patch("time.sleep", side_effect=slept.append):
        c.request("GET", "/api/v1/countries")
    assert slept == [retry_after]
    assert counter[0] == 2


@given(
    max_retries=st.integers(min_value=0, max_value=3),
    initial_delay=st.floats(min_value=0.01, max_value=2.0),
    backoff_factor=st.floats(min_value=1.0, max_value=3.0),
    max_delay=st.floats(min_value=0.01, max_value=10.0),
    attempts=st.lists(
        st.integers(min_value=0, max_value=10),
        min_size=1,
        max_size=4,
    ),
)
@settings(max_examples=50, deadline=None)
def test_compute_delay_bounds(max_retries, initial_delay, backoff_factor, max_delay, attempts):
    policy = RetryPolicy(
        max_retries=max_retries,
        initial_delay=initial_delay,
        backoff_factor=backoff_factor,
        max_delay=max_delay,
    )
    for attempt in attempts:
        delay = policy.compute_delay(attempt, retry_after=None)
        assert 0 <= delay <= max_delay
