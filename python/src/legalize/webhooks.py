"""Webhook signature verification.

Mirrors the server logic in
``web/src/legalize/web/db_webhooks.py:compute_signature``. The scheme
is Stripe-shaped:

- Signed content is ``f"{timestamp}.{raw_json_body}"``.
- Algorithm: HMAC-SHA256, hex-encoded.
- Header value: ``v1=<hex>`` (a future ``v2`` scheme can coexist).
- Replay protection: reject if the header timestamp is more than
  ``tolerance`` seconds away from ``now``. Default tolerance is 5
  minutes, matching the server's defaults.

The entry point is :meth:`Webhook.verify`. It returns a parsed
:class:`WebhookEvent` on success and raises
:class:`legalize.WebhookVerificationError` on any failure. The error
message is deliberately generic to avoid leaking which specific check
tripped.

Usage (Flask)::

    from legalize.webhooks import Webhook, WebhookVerificationError

    @app.post("/webhooks/legalize")
    def incoming():
        try:
            event = Webhook.verify(
                payload=request.get_data(),
                sig_header=request.headers["X-Legalize-Signature"],
                timestamp=request.headers["X-Legalize-Timestamp"],
                secret=os.environ["LEGALIZE_WHSEC"],
            )
        except WebhookVerificationError:
            return "", 400
        if event.type == "law.updated":
            ...
        return "", 204
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any

from legalize._errors import WebhookVerificationError

DEFAULT_TOLERANCE_SECONDS = 300  # 5 minutes — matches server
SUPPORTED_SCHEMES = ("v1",)


@dataclass(frozen=True)
class WebhookEvent:
    """A verified webhook event payload.

    Attributes:
        id: server-assigned event id (``evt_...``).
        type: event type (``law.created``, ``law.updated``, ``law.repealed``,
            ``reform.created``, ``test.ping``).
        created_at: ISO-8601 timestamp from the server.
        data: event-specific payload body.
        raw: the full decoded JSON body, kept for callers who need
            fields the SDK does not expose in a typed way.
    """

    id: str
    type: str
    created_at: str
    data: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> WebhookEvent:
        return cls(
            id=str(payload.get("id", "")),
            type=str(payload.get("event_type") or payload.get("type", "")),
            created_at=str(payload.get("created_at", "")),
            data=dict(payload.get("data") or {}),
            raw=dict(payload),
        )


class Webhook:
    """Namespace for webhook verification helpers."""

    TOLERANCE = DEFAULT_TOLERANCE_SECONDS

    @staticmethod
    def compute_signature(secret: str, payload: bytes, timestamp: str) -> str:
        """Return the canonical ``v1=<hex>`` signature for (payload, timestamp).

        Kept public to let callers generate test vectors or implement
        custom verification flows. Uses ``bytes`` for the payload so
        callers do not need to worry about Unicode normalization.
        """
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise TypeError("payload must be bytes")
        signed = timestamp.encode() + b"." + bytes(payload)
        sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return f"v1={sig}"

    @classmethod
    def verify(
        cls,
        *,
        payload: bytes | str,
        sig_header: str,
        timestamp: str,
        secret: str,
        tolerance: int | None = None,
        now: float | None = None,
    ) -> WebhookEvent:
        """Verify a webhook delivery and return the parsed event.

        Args:
            payload: the raw request body as the server sent it. Passing
                a re-serialized dict will NOT verify — the bytes must
                be the unmodified request body.
            sig_header: the ``X-Legalize-Signature`` header value. May
                contain several ``vN=<hex>`` pairs separated by commas.
            timestamp: the ``X-Legalize-Timestamp`` header value, an
                integer number of seconds since the Unix epoch encoded
                as a string.
            secret: the endpoint signing secret (``whsec_...``).
            tolerance: seconds of clock skew to accept in either
                direction. Defaults to :attr:`Webhook.TOLERANCE`.
            now: unit-test hook. Override the reference wall clock.

        Raises:
            WebhookVerificationError: on any verification failure.
        """
        if not sig_header or not timestamp or not secret:
            raise WebhookVerificationError("verification failed")

        payload_bytes = payload.encode() if isinstance(payload, str) else bytes(payload)

        # ---- timestamp check (anti-replay) ------------------------------
        try:
            ts_int = int(timestamp)
        except (TypeError, ValueError) as exc:
            raise WebhookVerificationError("verification failed") from exc

        tol = cls.TOLERANCE if tolerance is None else tolerance
        reference = time.time() if now is None else now
        if abs(reference - ts_int) > tol:
            raise WebhookVerificationError("verification failed")

        # ---- signature check --------------------------------------------
        expected = cls.compute_signature(secret, payload_bytes, timestamp)
        # Expected has the form "v1=<hex>". Extract just the hex for
        # constant-time comparison against each scheme match in the header.
        _, _, expected_hex = expected.partition("=")

        candidate_hexes = _extract_scheme_hexes(sig_header)
        if not candidate_hexes:
            raise WebhookVerificationError("verification failed")

        if not any(
            hmac.compare_digest(expected_hex, candidate) for candidate in candidate_hexes
        ):
            raise WebhookVerificationError("verification failed")

        # ---- parse payload ----------------------------------------------
        try:
            parsed = json.loads(payload_bytes.decode())
        except (UnicodeDecodeError, ValueError) as exc:
            raise WebhookVerificationError("verification failed") from exc
        if not isinstance(parsed, dict):
            raise WebhookVerificationError("verification failed")
        return WebhookEvent.from_payload(parsed)


def _extract_scheme_hexes(header: str) -> list[str]:
    """Pull every ``vN=<hex>`` pair from a signature header.

    The server sends exactly one ``v1=<hex>`` today. Parsing multiple
    pairs lets us roll a ``v2`` scheme without rewriting this function.
    Unknown schemes are ignored.
    """
    hexes: list[str] = []
    for part in header.split(","):
        scheme, _, value = part.strip().partition("=")
        if scheme in SUPPORTED_SCHEMES and value:
            hexes.append(value.strip())
    return hexes


__all__ = [
    "DEFAULT_TOLERANCE_SECONDS",
    "Webhook",
    "WebhookEvent",
    "WebhookVerificationError",
]
