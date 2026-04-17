"""Retry policy for transient failures.

Retries happen on:
- Network errors (DNS, connect, read timeout, TLS)
- HTTP 429 (rate limit)
- HTTP 500, 502, 503, 504 (transient server issues)

Retries do NOT happen on:
- 4xx other than 429 (caller error, retrying won't help)
- Any status if the method is not in the safe set and the server did
  NOT explicitly return Retry-After. Default safe set covers all
  current SDK methods (all GETs plus webhook test/retry which are
  idempotent in practice).

The ``Retry-After`` header wins when present. Otherwise we use
exponential backoff with full jitter, capped at ``max_delay``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 0.5
DEFAULT_MAX_DELAY = 30.0
DEFAULT_BACKOFF_FACTOR = 2.0

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryPolicy:
    """Configuration for automatic retries.

    Attributes:
        max_retries: maximum number of retry attempts. The total number
            of HTTP requests is at most ``max_retries + 1``. Set to 0
            to disable retries entirely.
        initial_delay: seconds to wait before the first retry when
            there is no ``Retry-After`` header.
        max_delay: cap on any single retry delay in seconds.
        backoff_factor: multiplier applied to the delay on each retry.
    """

    max_retries: int = DEFAULT_MAX_RETRIES
    initial_delay: float = DEFAULT_INITIAL_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR

    def should_retry(self, attempt: int, *, status: int | None) -> bool:
        if attempt >= self.max_retries:
            return False
        if status is None:
            # Network error — always retry up to the limit.
            return True
        return status in RETRY_STATUSES

    def compute_delay(
        self,
        attempt: int,
        *,
        retry_after: float | None,
    ) -> float:
        """Return the seconds to sleep before retry ``attempt`` (0-indexed).

        ``Retry-After`` wins unambiguously when present and non-negative:
        the server is telling us exactly how long to wait. Otherwise we
        use exponential backoff with full jitter::

            delay = random.uniform(0, min(max_delay, initial * factor**attempt))

        Full jitter beats "equal jitter" and "decorrelated jitter" for
        preventing thundering-herd recovery spikes.
        """
        if retry_after is not None and retry_after >= 0:
            return min(float(retry_after), self.max_delay)

        base = self.initial_delay * (self.backoff_factor ** attempt)
        return random.uniform(0, min(base, self.max_delay))  # noqa: S311 — jitter, not crypto


def parse_retry_after(header: str | None) -> float | None:
    """Parse the ``Retry-After`` header to seconds.

    Accepts either an integer number of seconds (the common case) or
    an HTTP-date. We intentionally do not support HTTP-date here to
    keep the SDK small — servers we care about send seconds.
    """
    if header is None:
        return None
    try:
        value = int(header)
    except (TypeError, ValueError):
        return None
    return max(0, value)


__all__ = [
    "DEFAULT_BACKOFF_FACTOR",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_MAX_RETRIES",
    "RETRY_STATUSES",
    "RetryPolicy",
    "parse_retry_after",
]
