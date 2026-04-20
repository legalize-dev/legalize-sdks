"""Edge cases in client request path: 204, non-JSON body, transport errors."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest

from legalize import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncLegalize,
    Legalize,
    RetryPolicy,
)


class TestNoContent:
    def test_sync_204(self, client, handler):
        handler[0] = lambda req: httpx.Response(204)
        assert client.request("DELETE", "/api/v1/webhooks/1") is None

    def test_sync_empty_body(self, client, handler):
        handler[0] = lambda req: httpx.Response(200, content=b"")
        assert client.request("GET", "/x") is None

    @pytest.mark.asyncio
    async def test_async_204(self, aclient, handler):
        handler[0] = lambda req: httpx.Response(204)
        assert await aclient.request("DELETE", "/api/v1/webhooks/1") is None
        await aclient.aclose()

    @pytest.mark.asyncio
    async def test_async_empty_body(self, aclient, handler):
        handler[0] = lambda req: httpx.Response(200, content=b"")
        assert await aclient.request("GET", "/x") is None
        await aclient.aclose()


class TestNonJSONBody:
    def test_sync_raises_apierror(self, client, handler):
        handler[0] = lambda req: httpx.Response(
            200, content=b"<html>oops</html>", headers={"content-type": "text/html"}
        )
        with pytest.raises(APIError, match="non-JSON"):
            client.request("GET", "/x")

    @pytest.mark.asyncio
    async def test_async_raises_apierror(self, aclient, handler):
        def h(_req):
            return httpx.Response(
                200, content=b"<html>oops</html>", headers={"content-type": "text/html"}
            )

        handler[0] = h
        with pytest.raises(APIError, match="non-JSON"):
            await aclient.request("GET", "/x")
        await aclient.aclose()


class TestTransportErrors:
    def test_sync_timeout_no_retry(self):
        def handler(_req):
            raise httpx.ReadTimeout("slow")

        with (
            Legalize(
                api_key="leg_test",
                base_url="http://testserver",
                retry=RetryPolicy(max_retries=0),
                transport=httpx.MockTransport(handler),
            ) as c,
            pytest.raises(APITimeoutError),
        ):
            c.request("GET", "/x")

    def test_sync_connect_error_no_retry(self):
        def handler(_req):
            raise httpx.ConnectError("no route")

        with (
            Legalize(
                api_key="leg_test",
                base_url="http://testserver",
                retry=RetryPolicy(max_retries=0),
                transport=httpx.MockTransport(handler),
            ) as c,
            pytest.raises(APIConnectionError),
        ):
            c.request("GET", "/x")

    def test_sync_other_exception_reraises(self):
        def handler(_req):
            raise RuntimeError("unexpected")

        with (
            Legalize(
                api_key="leg_test",
                base_url="http://testserver",
                retry=RetryPolicy(max_retries=0),
                transport=httpx.MockTransport(handler),
            ) as c,
            pytest.raises(RuntimeError, match="unexpected"),
        ):
            c.request("GET", "/x")

    @pytest.mark.asyncio
    async def test_async_timeout_no_retry(self):
        def handler(_req):
            raise httpx.ReadTimeout("slow")

        async with AsyncLegalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=0),
            transport=httpx.MockTransport(handler),
        ) as c:
            with pytest.raises(APITimeoutError):
                await c.request("GET", "/x")

    @pytest.mark.asyncio
    async def test_async_connect_error_retries_and_gives_up(self):
        count = [0]

        def handler(_req):
            count[0] += 1
            raise httpx.ConnectError("no route")

        c = AsyncLegalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=1, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        try:
            with pytest.raises(APIConnectionError):
                await c.request("GET", "/x")
            # 1 original + 1 retry
            assert count[0] == 2
        finally:
            await c.aclose()


class TestAsyncRetryBranches:
    @pytest.mark.asyncio
    async def test_async_retries_on_500(self):
        responses = [
            httpx.Response(500, json={"detail": "err"}),
            httpx.Response(500, json={"detail": "err"}),
            httpx.Response(200, json={}),
        ]
        idx = [0]

        def handler(_req):
            r = responses[idx[0]]
            idx[0] += 1
            return r

        c = AsyncLegalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=3, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        try:
            with mock.patch("asyncio.sleep") as sleep_mock:
                sleep_mock.return_value = None

                async def noop_sleep(_delay):
                    return None

                sleep_mock.side_effect = noop_sleep
                result = await c.request("GET", "/x")
            assert result == {}
            assert idx[0] == 3
        finally:
            await c.aclose()

    @pytest.mark.asyncio
    async def test_async_gives_up_after_retries(self):
        responses = [httpx.Response(502, json={"detail": "bad"})] * 5
        idx = [0]

        def handler(_req):
            r = responses[idx[0]]
            idx[0] += 1
            return r

        c = AsyncLegalize(
            api_key="leg_test",
            base_url="http://testserver",
            retry=RetryPolicy(max_retries=2, initial_delay=0, max_delay=0),
            transport=httpx.MockTransport(handler),
        )
        try:

            async def noop_sleep(_delay):
                return None

            with mock.patch("asyncio.sleep", side_effect=noop_sleep):
                with pytest.raises(APIError):
                    await c.request("GET", "/x")
            # max_retries=2 → 1 initial + 2 retries = 3 calls
            assert idx[0] == 3
        finally:
            await c.aclose()


class TestLastResponse:
    def test_none_before_any_request(self):
        with Legalize(api_key="leg_test", base_url="http://x") as c:
            assert c.last_response is None

    def test_populated_after_request(self, client, handler):
        handler[0] = lambda req: httpx.Response(
            200, json={}, headers={"x-ratelimit-remaining": "99"}
        )
        client.request("GET", "/x")
        assert client.last_response is not None
        assert client.last_response.headers["x-ratelimit-remaining"] == "99"

    @pytest.mark.asyncio
    async def test_async_populated_after_request(self, aclient, handler):
        handler[0] = lambda req: httpx.Response(200, json={})
        await aclient.request("GET", "/x")
        assert aclient.last_response is not None
        await aclient.aclose()
