"""Retry policy for transient failures.

Retries happen on:
- Network errors (DNS, connect, read timeout, TLS)
- HTTP 429 (rate limit)
- HTTP 500, 502, 503, 504 (transient server issues)

Retries do NOT happen on:
- 4xx other than 429 (caller error, retrying won't help).
- Non-idempotent HTTP methods (POST, PATCH) unless the caller opts in.
  Blindly retrying a POST can create duplicate resources — e.g. two
  webhook endpoints, two delivery retries. Safe set is
  ``{GET, HEAD, OPTIONS, PUT, DELETE}``.

The ``Retry-After`` header wins when present. Otherwise we use
exponential backoff with full jitter, capped at ``max_delay``.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_DELAY = 0.5
DEFAULT_MAX_DELAY = 30.0
DEFAULT_BACKOFF_FACTOR = 2.0

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# HTTP methods the SDK retries by default. POST and PATCH are NOT in
# this set because retrying them can duplicate server-side effects
# (e.g. two webhook endpoints from one webhooks.create call). Callers
# that know a specific POST is idempotent can opt in via
# ``RetryPolicy(retry_non_idempotent=True)``.
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


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
        retry_non_idempotent: when ``False`` (default), POST and PATCH
            are never retried — even on 429/5xx — because the server
            may have already applied the write. Opt in per policy if
            the target endpoint is known to be idempotent.
    """

    max_retries: int = DEFAULT_MAX_RETRIES
    initial_delay: float = DEFAULT_INITIAL_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    retry_non_idempotent: bool = False

    def should_retry(
        self,
        attempt: int,
        *,
        status: int | None,
        method: str = "GET",
    ) -> bool:
        if attempt >= self.max_retries:
            return False
        if not self.retry_non_idempotent and method.upper() not in IDEMPOTENT_METHODS:
            return False
        if status is None:
            # Network error — retry up to the limit, still respecting
            # the idempotency gate above.
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

        base = self.initial_delay * (self.backoff_factor**attempt)
        return random.uniform(0, min(base, self.max_delay))  # noqa: S311 — jitter, not crypto


def parse_retry_after(header: str | None) -> float | None:
    """Parse the ``Retry-After`` header to seconds.

    RFC 9110 allows two forms:

    - A non-negative integer (delta-seconds): ``Retry-After: 120``.
    - An HTTP-date: ``Retry-After: Wed, 21 Oct 2025 07:28:00 GMT``.

    We accept both. Unparseable input returns ``None`` so the caller
    can fall back to its own backoff policy. HTTP-date values in the
    past clamp to ``0``.
    """
    if header is None:
        return None
    header = header.strip()
    if not header:
        return None
    # Delta-seconds form (must be all digits; negative values not allowed).
    try:
        value = int(header)
    except ValueError:
        pass
    else:
        return float(max(0, value))
    # HTTP-date form.
    try:
        dt = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return None
    delta = dt.timestamp() - time.time()
    return max(0.0, delta)


__all__ = [
    "DEFAULT_BACKOFF_FACTOR",
    "DEFAULT_INITIAL_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_MAX_RETRIES",
    "IDEMPOTENT_METHODS",
    "RETRY_STATUSES",
    "RetryPolicy",
    "parse_retry_after",
]
