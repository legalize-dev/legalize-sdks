"""Webhook retry end-to-end: failed delivery → manual retry.

Points the endpoint at ``httpbin.org/status/500`` so every delivery
fails. We then exercise the server's delivery list + manual retry
via the SDK and assert the attempt counter grows.

If httpbin.org is down, the test is skipped — it's not the SDK's job
to keep third-party fixtures alive.
"""

from __future__ import annotations

import time

import httpx
import pytest

from legalize import Legalize

HTTPBIN_500 = "https://httpbin.org/status/500"


@pytest.fixture(scope="module", autouse=True)
def _httpbin_reachable() -> None:
    try:
        httpx.head(HTTPBIN_500, timeout=5.0)
    except httpx.HTTPError as e:
        pytest.skip(f"httpbin.org unreachable: {e}")


def test_failed_delivery_then_manual_retry(client: Legalize, test_prefix: str):
    endpoint = client.webhooks.create(
        url=HTTPBIN_500,
        event_types=["law.updated"],
        description=test_prefix,
    )
    endpoint_id = int(endpoint["id"])
    try:
        # Trigger a test.ping that will definitely fail upstream.
        result = client.webhooks.test(endpoint_id)
        # status may be "failed" immediately (sync delivery) — either way the
        # response_status from httpbin should be 500.
        assert result.get("response_status") == 500, result

        # Give the server a moment to persist the delivery row.
        for _ in range(10):
            failed = client.webhooks.deliveries(endpoint_id, status="failed")
            if failed.get("total", 0) >= 1:
                break
            time.sleep(0.5)
        else:
            pytest.fail(f"no failed delivery recorded: {failed}")

        delivery = failed["deliveries"][0]
        initial_attempts = int(delivery.get("attempts", 0))
        delivery_id = int(delivery["id"])
        assert initial_attempts >= 1

        # Manually retry — SDK path we want to verify.
        retry_result = client.webhooks.retry(endpoint_id, delivery_id)
        assert retry_result.get("status") == "failed", retry_result
        assert retry_result.get("attempts", 0) > initial_attempts

        # The delivery list should reflect the new attempt count.
        failed_after = client.webhooks.deliveries(endpoint_id, status="failed")
        updated = next(
            (d for d in failed_after["deliveries"] if int(d["id"]) == delivery_id),
            None,
        )
        assert updated is not None
        assert int(updated["attempts"]) > initial_attempts
    finally:
        try:
            client.webhooks.delete(endpoint_id)
        except Exception:  # noqa: S110 — best-effort cleanup
            pass
