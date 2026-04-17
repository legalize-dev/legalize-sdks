"""HTTP client core — sync (:class:`Legalize`) and async (:class:`AsyncLegalize`).

Both clients share a single base class that builds requests, executes
them under the retry policy, and maps server responses to either
Pydantic models or the error hierarchy. Transport is ``httpx``.

Design notes:

- Auth is a single ``Authorization: Bearer <key>`` header. The key
  format (``leg_*``) is validated client-side so obviously-bad inputs
  raise :class:`AuthenticationError` before hitting the network.
- Every request sends ``Legalize-API-Version`` so the SDK version can
  evolve independently from the API version.
- Every request sends a ``User-Agent`` identifying SDK + Python version
  for server-side analytics.
- Rate-limit headers (``X-RateLimit-*``) are exposed via the last
  response for callers that want to inspect them.
- Connection + read timeouts are separate, mirroring httpx.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from types import TracebackType
from typing import Any, TypeVar

import httpx

from legalize._errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
)
from legalize._retry import RetryPolicy, parse_retry_after
from legalize._version import __version__

DEFAULT_BASE_URL = "https://legalize.dev"
DEFAULT_API_VERSION = "v1"
DEFAULT_TIMEOUT = 30.0

KEY_PREFIX = "leg_"

T = TypeVar("T")


def _default_user_agent() -> str:
    return (
        f"legalize-python/{__version__} "
        f"python/{platform.python_version()} "
        f"{platform.system().lower()}"
    )


def _resolve_api_key(api_key: str | None) -> str:
    key = api_key if api_key is not None else os.environ.get("LEGALIZE_API_KEY")
    if not key:
        raise AuthenticationError(
            "Missing API key. Pass api_key=... or set LEGALIZE_API_KEY.",
            status_code=401,
            code="missing_api_key",
        )
    if not key.startswith(KEY_PREFIX):
        raise AuthenticationError(
            f"API key format unrecognized. Keys start with {KEY_PREFIX!r}.",
            status_code=401,
            code="invalid_api_key",
        )
    return key


def _build_headers(api_key: str, api_version: str, extra: dict[str, str] | None) -> dict[str, str]:
    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": _default_user_agent(),
        "Legalize-API-Version": api_version,
        "Accept": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _raise_for_transport_error(exc: Exception) -> None:
    if isinstance(exc, httpx.TimeoutException):
        raise APITimeoutError(str(exc) or "request timed out", cause=exc) from exc
    if isinstance(exc, httpx.TransportError):
        raise APIConnectionError(str(exc) or "transport error", cause=exc) from exc


class _BaseClient:
    """Shared configuration + request-building logic.

    Concrete subclasses implement :meth:`_send` to perform the actual
    HTTP I/O (sync or async). Everything else is transport-agnostic.
    """

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        api_version: str,
        timeout: float | httpx.Timeout,
        retry: RetryPolicy,
        default_headers: dict[str, str] | None,
    ) -> None:
        self._api_key = _resolve_api_key(api_key)
        self._base_url = base_url.rstrip("/")
        self._api_version = api_version
        self._timeout = timeout
        self._retry = retry
        self._headers = _build_headers(self._api_key, api_version, default_headers)

    # ---- URL building ----------------------------------------------------

    def _build_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        # Callers pass the full API path (e.g. "/api/v1/countries").
        # We do NOT auto-prefix — resources are explicit to keep the
        # surface inspectable.
        return self._base_url + path

    def _build_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Request:
        url = self._build_url(path)
        headers = dict(self._headers)
        if extra_headers:
            headers.update(extra_headers)
        clean_params = _clean_params(params) if params else None
        return httpx.Request(
            method=method.upper(),
            url=url,
            params=clean_params,
            json=json,
            headers=headers,
        )


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop None values; coerce bools to 'true'/'false'; stringify dates.

    The Legalize API expects bare values in the query string. Pydantic
    models are not accepted as params (always flatten before passing
    to the transport layer).
    """
    out: dict[str, Any] = {}
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = "true" if v else "false"
        elif isinstance(v, (list, tuple)):
            if v:
                out[k] = ",".join(str(x) for x in v)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


class Legalize(_BaseClient):
    """Synchronous client for the Legalize API.

    Example::

        from legalize import Legalize

        client = Legalize(api_key="leg_...")
        countries = client.countries.list()

    Use as a context manager to ensure the underlying HTTP connection
    pool is released::

        with Legalize(api_key="leg_...") as client:
            ...
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str = DEFAULT_API_VERSION,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int | None = None,
        retry: RetryPolicy | None = None,
        default_headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        policy = _resolve_retry_policy(retry, max_retries)
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            api_version=api_version,
            timeout=timeout,
            retry=policy,
            default_headers=default_headers,
        )
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )
        self._last_response: httpx.Response | None = None
        self._bind_resources()

    # ---- resources -------------------------------------------------------

    def _bind_resources(self) -> None:
        # Imports are local to avoid a circular dependency at module load.
        from legalize.resources.countries import Countries
        from legalize.resources.jurisdictions import Jurisdictions
        from legalize.resources.law_types import LawTypes
        from legalize.resources.laws import Laws
        from legalize.resources.reforms import Reforms
        from legalize.resources.stats import Stats
        from legalize.resources.webhooks import Webhooks

        self.countries = Countries(self)
        self.jurisdictions = Jurisdictions(self)
        self.law_types = LawTypes(self)
        self.laws = Laws(self)
        self.reforms = Reforms(self)
        self.stats = Stats(self)
        self.webhooks = Webhooks(self)

    # ---- lifecycle -------------------------------------------------------

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Legalize:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ---- request ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """Execute a request, apply retries, return parsed JSON.

        Raises a subclass of :class:`APIError` on any non-2xx response
        and :class:`APIConnectionError` on transport failure.
        """
        request = self._build_request(
            method, path, params=params, json=json, extra_headers=extra_headers
        )
        response = self._send_with_retry(request)
        self._last_response = response
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise APIError(
                "Server returned non-JSON body",
                status_code=response.status_code,
                body=response.content,
                response=response,
            ) from exc

    def _send_with_retry(self, request: httpx.Request) -> httpx.Response:
        last_exc: Exception | None = None
        attempt = 0
        while True:
            try:
                response = self._http.send(request)
            except Exception as exc:
                if not self._retry.should_retry(attempt, status=None):
                    _raise_for_transport_error(exc)
                    raise
                last_exc = exc
                delay = self._retry.compute_delay(attempt, retry_after=None)
                time.sleep(delay)
                attempt += 1
                continue

            if 200 <= response.status_code < 300:
                return response

            if not self._retry.should_retry(attempt, status=response.status_code):
                raise APIError.from_response(response)

            retry_after = parse_retry_after(response.headers.get("retry-after"))
            delay = self._retry.compute_delay(attempt, retry_after=retry_after)
            response.close()
            time.sleep(delay)
            attempt += 1
            # last_exc kept in case we exhaust; last server response already closed.
            _ = last_exc

    @property
    def last_response(self) -> httpx.Response | None:
        """The most recent raw response, for inspecting rate-limit headers.

        Returns None before any request has been issued.
        """
        return self._last_response


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class AsyncLegalize(_BaseClient):
    """Asynchronous client for the Legalize API.

    Example::

        import asyncio
        from legalize import AsyncLegalize

        async def main():
            async with AsyncLegalize(api_key="leg_...") as client:
                countries = await client.countries.list()

        asyncio.run(main())
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        api_version: str = DEFAULT_API_VERSION,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int | None = None,
        retry: RetryPolicy | None = None,
        default_headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        policy = _resolve_retry_policy(retry, max_retries)
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            api_version=api_version,
            timeout=timeout,
            retry=policy,
            default_headers=default_headers,
        )
        self._http = httpx.AsyncClient(
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )
        self._last_response: httpx.Response | None = None
        self._bind_resources()

    def _bind_resources(self) -> None:
        from legalize.resources.countries import AsyncCountries
        from legalize.resources.jurisdictions import AsyncJurisdictions
        from legalize.resources.law_types import AsyncLawTypes
        from legalize.resources.laws import AsyncLaws
        from legalize.resources.reforms import AsyncReforms
        from legalize.resources.stats import AsyncStats
        from legalize.resources.webhooks import AsyncWebhooks

        self.countries = AsyncCountries(self)
        self.jurisdictions = AsyncJurisdictions(self)
        self.law_types = AsyncLawTypes(self)
        self.laws = AsyncLaws(self)
        self.reforms = AsyncReforms(self)
        self.stats = AsyncStats(self)
        self.webhooks = AsyncWebhooks(self)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> AsyncLegalize:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        import asyncio

        request = self._build_request(
            method, path, params=params, json=json, extra_headers=extra_headers
        )
        attempt = 0
        while True:
            try:
                response = await self._http.send(request)
            except Exception as exc:
                if not self._retry.should_retry(attempt, status=None):
                    _raise_for_transport_error(exc)
                    raise
                delay = self._retry.compute_delay(attempt, retry_after=None)
                await asyncio.sleep(delay)
                attempt += 1
                continue

            if 200 <= response.status_code < 300:
                self._last_response = response
                if response.status_code == 204 or not response.content:
                    return None
                try:
                    return response.json()
                except ValueError as exc:
                    raise APIError(
                        "Server returned non-JSON body",
                        status_code=response.status_code,
                        body=response.content,
                        response=response,
                    ) from exc

            if not self._retry.should_retry(attempt, status=response.status_code):
                raise APIError.from_response(response)

            retry_after = parse_retry_after(response.headers.get("retry-after"))
            delay = self._retry.compute_delay(attempt, retry_after=retry_after)
            await response.aclose()
            await asyncio.sleep(delay)
            attempt += 1

    @property
    def last_response(self) -> httpx.Response | None:
        return self._last_response


def _resolve_retry_policy(policy: RetryPolicy | None, max_retries: int | None) -> RetryPolicy:
    """Resolve the retry configuration from the two caller knobs.

    ``retry=...`` (explicit policy) wins over ``max_retries=...`` when
    both are passed. The convenience kwarg exists for the common case
    of wanting to tweak just the retry count without building a policy.
    """
    if policy is not None:
        return policy
    if max_retries is None:
        return RetryPolicy()
    return RetryPolicy(max_retries=max_retries)


__all__ = [
    "DEFAULT_API_VERSION",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "AsyncLegalize",
    "Legalize",
]


# Silence unused-import warnings; sys and TypeVar are part of stable API shape
# (kept importable for tests that probe module attrs).
_ = (sys, TypeVar)
