"""Cross-verify SDK signature computation against server implementation.

The server's ``compute_signature`` lives in
``web/src/legalize/web/db_webhooks.py``. We re-implement its exact
byte-level contract here as ``_server_compute`` and assert equivalence
on a wide set of inputs.

If this test ever fails, one of two things happened:
1. The server changed its signing scheme (intentional or not), OR
2. The SDK drifted. Either way a PR should realign them explicitly.
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from legalize.webhooks import Webhook


def _server_compute(secret: str, payload_bytes: bytes, timestamp: str) -> str:
    """Verbatim port of web/src/legalize/web/db_webhooks.py:compute_signature."""
    signed_content = f"{timestamp}.{payload_bytes.decode()}"
    sig = hmac.new(secret.encode(), signed_content.encode(), hashlib.sha256).hexdigest()
    return f"v1={sig}"


@pytest.mark.parametrize(
    "secret, payload, timestamp",
    [
        ("whsec_short", b"{}", "1713360000"),
        (
            "whsec_" + "a" * 43,
            b'{"id":"evt_1","event_type":"law.updated","data":{}}',
            "1713360000",
        ),
        (
            "whsec_\u00e9\u00e8\u00f1",  # non-ASCII secret
            '{"id":"evt_1","data":{"x":"caf\u00e9"}}'.encode(),  # non-ASCII JSON body
            "0",
        ),
        (
            "whsec_empty_payload",
            b"",
            "1",
        ),
        (
            "whsec_newlines",
            b'{"a":1}\n',
            "999999999",
        ),
    ],
)
def test_sdk_matches_server(secret, payload, timestamp):
    assert Webhook.compute_signature(secret, payload, timestamp) == _server_compute(
        secret, payload, timestamp
    )


def test_signature_format():
    sig = Webhook.compute_signature("whsec_test", b"{}", "100")
    assert sig.startswith("v1=")
    assert len(sig) == 3 + 64  # v1= + sha256 hex


def test_signature_requires_bytes():
    with pytest.raises(TypeError):
        Webhook.compute_signature("whsec_test", "not bytes", "100")  # type: ignore[arg-type]


def test_deterministic():
    a = Webhook.compute_signature("s", b"x", "1")
    b = Webhook.compute_signature("s", b"x", "1")
    assert a == b


def test_changes_with_any_input():
    base = Webhook.compute_signature("s", b"x", "1")
    assert Webhook.compute_signature("s2", b"x", "1") != base
    assert Webhook.compute_signature("s", b"y", "1") != base
    assert Webhook.compute_signature("s", b"x", "2") != base


def test_bytearray_and_memoryview_accepted():
    expected = Webhook.compute_signature("s", b"abc", "1")
    assert Webhook.compute_signature("s", bytearray(b"abc"), "1") == expected
    assert Webhook.compute_signature("s", memoryview(b"abc"), "1") == expected
