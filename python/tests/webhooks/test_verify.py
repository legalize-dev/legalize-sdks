"""Webhook.verify — happy path, tampering, replay, skew, malformed input.

The error message from verify() is deliberately generic. Tests assert
on the exception TYPE, not the message, to mirror the production
contract. (Leaking which check failed helps attackers iterate.)
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from legalize import Webhook, WebhookEvent, WebhookVerificationError

SECRET = "whsec_unit_test_secret_with_some_length"
NOW = 1_800_000_000  # fixed reference time for all tests


def _sign(secret: str, payload: bytes, timestamp: str) -> str:
    return Webhook.compute_signature(secret, payload, timestamp)


def _payload(id_="evt_1", event_type="law.updated", data=None) -> bytes:
    return json.dumps(
        {
            "id": id_,
            "event_type": event_type,
            "created_at": "2026-04-01T00:00:00Z",
            "data": data or {"law_id": "ley_organica_3_2018"},
        }
    ).encode()


# ---- happy path --------------------------------------------------------


class TestVerifyHappy:
    def test_returns_event(self):
        p = _payload()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)

        event = Webhook.verify(
            payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW
        )

        assert isinstance(event, WebhookEvent)
        assert event.id == "evt_1"
        assert event.type == "law.updated"
        assert event.data == {"law_id": "ley_organica_3_2018"}

    def test_accepts_str_payload(self):
        p = _payload()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)

        event = Webhook.verify(
            payload=p.decode(), sig_header=sig, timestamp=ts, secret=SECRET, now=NOW
        )
        assert event.id == "evt_1"

    def test_accepts_multiple_schemes_in_header(self):
        p = _payload()
        ts = str(NOW)
        v1 = _sign(SECRET, p, ts)
        # Server might also include a hypothetical v0 legacy signature;
        # SDK should ignore unknown schemes and accept v1.
        header = f"v0=abcdef, {v1}"

        event = Webhook.verify(
            payload=p, sig_header=header, timestamp=ts, secret=SECRET, now=NOW
        )
        assert event.id == "evt_1"

    def test_event_type_alias(self):
        # Server sends "event_type"; SDK exposes as .type
        p = json.dumps({"id": "x", "event_type": "test.ping", "created_at": "t", "data": {}}).encode()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        event = Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)
        assert event.type == "test.ping"


# ---- tampering ---------------------------------------------------------


class TestTampering:
    def test_wrong_secret(self):
        p = _payload()
        ts = str(NOW)
        sig = _sign("whsec_attacker", p, ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)

    def test_tampered_payload(self):
        p = _payload()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        tampered = p.replace(b"ley_organica_3_2018", b"bogus")
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=tampered, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)

    def test_tampered_timestamp(self):
        p = _payload()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(
                payload=p, sig_header=sig, timestamp=str(NOW + 1), secret=SECRET, now=NOW
            )

    def test_malformed_signature_hex(self):
        p = _payload()
        ts = str(NOW)
        # valid length but random hex
        bogus = "v1=" + "f" * 64
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p, sig_header=bogus, timestamp=ts, secret=SECRET, now=NOW)

    def test_extra_byte_appended_to_payload(self):
        p = _payload()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p + b" ", sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)


# ---- replay / clock skew ----------------------------------------------


class TestReplay:
    def test_rejects_old_timestamp(self):
        p = _payload()
        old_ts = str(NOW - 3600)  # 1h old, way outside 5min tolerance
        sig = _sign(SECRET, p, old_ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p, sig_header=sig, timestamp=old_ts, secret=SECRET, now=NOW)

    def test_rejects_future_timestamp(self):
        p = _payload()
        future_ts = str(NOW + 3600)
        sig = _sign(SECRET, p, future_ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p, sig_header=sig, timestamp=future_ts, secret=SECRET, now=NOW)

    def test_accepts_small_skew(self):
        p = _payload()
        ts = str(NOW - 30)  # 30s earlier — well within default tolerance
        sig = _sign(SECRET, p, ts)
        event = Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)
        assert event.id == "evt_1"

    def test_boundary_tolerance(self):
        p = _payload()
        # Exactly at the boundary: |skew| == tolerance must pass (<= not <)
        ts = str(NOW - Webhook.TOLERANCE)
        sig = _sign(SECRET, p, ts)
        event = Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)
        assert event.id == "evt_1"

    def test_custom_tolerance(self):
        p = _payload()
        ts = str(NOW - 10)
        sig = _sign(SECRET, p, ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(
                payload=p,
                sig_header=sig,
                timestamp=ts,
                secret=SECRET,
                now=NOW,
                tolerance=5,
            )


# ---- malformed / edge inputs ------------------------------------------


class TestMalformed:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"payload": b"{}", "sig_header": "", "timestamp": "1", "secret": SECRET},
            {"payload": b"{}", "sig_header": "v1=abc", "timestamp": "", "secret": SECRET},
            {"payload": b"{}", "sig_header": "v1=abc", "timestamp": "1", "secret": ""},
            {"payload": b"{}", "sig_header": "garbage", "timestamp": "1", "secret": SECRET},
            {"payload": b"{}", "sig_header": "v1=", "timestamp": "1", "secret": SECRET},
            {"payload": b"{}", "sig_header": "v2=abc", "timestamp": "1", "secret": SECRET},
        ],
    )
    def test_bad_inputs_raise(self, kwargs):
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(**kwargs, now=NOW)

    def test_non_integer_timestamp(self):
        p = _payload()
        sig = _sign(SECRET, p, "not-a-number")
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(
                payload=p,
                sig_header=sig,
                timestamp="not-a-number",
                secret=SECRET,
                now=NOW,
            )

    def test_non_json_payload(self):
        p = b"this is not json"
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)

    def test_non_dict_json_payload(self):
        p = b'["list", "not", "dict"]'
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        with pytest.raises(WebhookVerificationError):
            Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)


# ---- constant-time compare --------------------------------------------


class TestConstantTime:
    """Regression test: we must use hmac.compare_digest, not ``==``.

    Rather than benchmarking (flaky), we verify that the compare_digest
    call is in the code path by monkeypatching it and checking it runs.
    """

    def test_uses_hmac_compare_digest(self, monkeypatch):
        calls = {"n": 0}
        real_compare = hmac.compare_digest

        def counting(a, b):
            calls["n"] += 1
            return real_compare(a, b)

        monkeypatch.setattr("legalize.webhooks.hmac.compare_digest", counting)
        p = _payload()
        ts = str(NOW)
        sig = _sign(SECRET, p, ts)
        Webhook.verify(payload=p, sig_header=sig, timestamp=ts, secret=SECRET, now=NOW)
        assert calls["n"] >= 1

    def test_generic_error_message(self):
        """Do not leak which check failed."""
        messages: set[str] = set()

        def record(**kwargs):
            try:
                Webhook.verify(**kwargs, now=NOW)
            except WebhookVerificationError as e:
                messages.add(str(e))

        record(payload=b"{}", sig_header="", timestamp="1", secret=SECRET)
        record(payload=b"{}", sig_header="v1=" + "f" * 64, timestamp="1", secret=SECRET)
        record(
            payload=_payload(),
            sig_header=_sign(SECRET, _payload(), "0"),
            timestamp="0",
            secret=SECRET,
        )
        # All errors must share a single opaque message.
        assert len(messages) == 1


# ---- hashlib import dummy-use so linter is happy -----------------------
_ = hashlib
