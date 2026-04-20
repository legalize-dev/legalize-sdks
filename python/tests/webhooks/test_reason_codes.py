"""Regression: WebhookVerificationError.reason carries a machine-readable code.

Parity with Node (@legalize-dev/sdk) and Go SDKs — all three now
expose the same five reason codes so cross-language server-side
metrics line up. The public ``message`` stays generic for the usual
information-leak reason.
"""

from __future__ import annotations

import hashlib
import hmac
import time

import pytest

from legalize import Webhook, WebhookVerificationError

SECRET = "whsec_unit_test_secret_with_some_length"


def _sign(payload: bytes, ts: str, secret: str = SECRET) -> str:
    sig = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"v1={sig}"


def test_missing_header():
    with pytest.raises(WebhookVerificationError) as ei:
        Webhook.verify(payload=b"{}", sig_header="", timestamp="1", secret=SECRET)
    assert ei.value.reason == "missing_header"


def test_bad_timestamp():
    with pytest.raises(WebhookVerificationError) as ei:
        Webhook.verify(
            payload=b"{}", sig_header="v1=deadbeef", timestamp="not-a-number", secret=SECRET
        )
    assert ei.value.reason == "bad_timestamp"


def test_timestamp_outside_tolerance():
    ts = str(int(time.time()) - 10_000)  # way in the past
    with pytest.raises(WebhookVerificationError) as ei:
        Webhook.verify(payload=b"{}", sig_header=_sign(b"{}", ts), timestamp=ts, secret=SECRET)
    assert ei.value.reason == "timestamp_outside_tolerance"


def test_no_valid_signature():
    ts = str(int(time.time()))
    with pytest.raises(WebhookVerificationError) as ei:
        Webhook.verify(payload=b"{}", sig_header="garbage", timestamp=ts, secret=SECRET)
    assert ei.value.reason == "no_valid_signature"


def test_bad_signature():
    ts = str(int(time.time()))
    with pytest.raises(WebhookVerificationError) as ei:
        Webhook.verify(
            payload=b"{}",
            sig_header="v1=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            timestamp=ts,
            secret=SECRET,
        )
    assert ei.value.reason == "bad_signature"


def test_generic_message_does_not_leak_reason():
    """The exception message is uniform so it can be echoed to the
    HTTP client without telling an attacker which check failed."""
    ts = str(int(time.time()))
    with pytest.raises(WebhookVerificationError) as ei:
        Webhook.verify(payload=b"{}", sig_header="garbage", timestamp=ts, secret=SECRET)
    assert "no_valid_signature" not in str(ei.value)
    assert "garbage" not in str(ei.value)


def test_reason_codes_match_spec():
    """The five documented codes are all listed on the class."""
    assert WebhookVerificationError.REASONS == (
        "missing_header",
        "bad_timestamp",
        "timestamp_outside_tolerance",
        "no_valid_signature",
        "bad_signature",
    )
