"""Error hierarchy for the Legalize SDK.

The server returns two error shapes:

1. Structured dict from the API layer::

       {"detail": {"error": "quota_exceeded",
                   "message": "Monthly quota of 10000 requests exceeded.",
                   "limit": 10000,
                   "retry_after": 3600,
                   "upgrade_url": "https://legalize.dev/pricing"}}

2. FastAPI validation errors (422)::

       {"detail": [{"loc": [...], "msg": "...", "type": "..."}, ...]}

3. Plain string detail for simple 404/400::

       {"detail": "Law not found: xyz"}

``APIError.from_response`` normalizes all three into an instance of the
most specific subclass, keeping the raw body available on ``.body`` and
the parsed structured payload on ``.data``.
"""

from __future__ import annotations

from typing import Any

import httpx

from legalize._retry import parse_retry_after


class LegalizeError(Exception):
    """Base for everything the SDK raises."""


class APIError(LegalizeError):
    """HTTP error from the API.

    Attributes:
        status_code: HTTP status code, or None for transport errors.
        code: the server-provided error code (``invalid_api_key``,
            ``quota_exceeded``, ...) when available.
        message: human-readable message from the server, or a default.
        body: raw response body as bytes (may be empty).
        data: parsed JSON body, or None.
        request_id: value of the ``X-Request-Id`` response header.
        response: the underlying ``httpx.Response`` for advanced use.
    """

    status_code: int | None = None

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
        body: bytes = b"",
        data: Any = None,
        request_id: str | None = None,
        response: httpx.Response | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.body = body
        self.data = data
        self.request_id = request_id
        self.response = response
        if status_code is not None:
            self.status_code = status_code

    def __str__(self) -> str:
        parts: list[str] = []
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        if self.code:
            parts.append(self.code)
        parts.append(self.message)
        if self.request_id:
            parts.append(f"(request_id={self.request_id})")
        return " ".join(parts)

    @classmethod
    def from_response(cls, response: httpx.Response) -> APIError:
        """Build the most specific APIError subclass for a response."""
        body = response.content or b""
        data: Any = None
        try:
            data = response.json() if body else None
        except ValueError:
            data = None

        code, message, extras = _parse_error_body(data, response)
        request_id = response.headers.get("x-request-id")
        status = response.status_code

        error_cls = _pick_error_class(status, code)
        err = error_cls(
            message,
            status_code=status,
            code=code,
            body=body,
            data=data,
            request_id=request_id,
            response=response,
        )
        for k, v in extras.items():
            setattr(err, k, v)
        return err


class AuthenticationError(APIError):
    """401 — missing, malformed, or invalid API key."""

    status_code = 401


class ForbiddenError(APIError):
    """403 — feature not available for the caller's tier."""

    status_code = 403


class NotFoundError(APIError):
    """404 — resource (country, law, webhook, ...) not found."""

    status_code = 404


class InvalidRequestError(APIError):
    """400 — malformed request parameters."""

    status_code = 400


class ValidationError(APIError):
    """422 — FastAPI request validation error.

    ``errors`` is the list of validation issues as returned by FastAPI.
    """

    status_code = 422

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.errors: list[dict[str, Any]] = []


class RateLimitError(APIError):
    """429 — burst or monthly quota exceeded.

    ``retry_after`` is parsed from either the server body or the
    ``Retry-After`` header, in seconds. ``limit`` is the applicable
    quota limit when provided by the server.
    """

    status_code = 429

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after: int | None = None
        self.limit: int | None = None


class ServerError(APIError):
    """5xx — upstream failure."""


class ServiceUnavailableError(ServerError):
    """503 — API temporarily unavailable (kill switch on)."""

    status_code = 503


class APIConnectionError(LegalizeError):
    """Network failure, DNS error, connection timeout, TLS error, etc.

    Raised instead of ``APIError`` when the request never reached a
    point where the server returned an HTTP status.
    """

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class APITimeoutError(APIConnectionError):
    """Request timed out without a response."""


class WebhookVerificationError(LegalizeError):
    """Raised by ``Webhook.verify`` when the signature is invalid.

    The public exception ``message`` is deliberately generic — do not
    surface it back to the webhook sender, since that helps attackers
    iterate. For server-side logging and metrics, inspect
    :attr:`reason`, which carries one of the machine-readable codes
    enumerated in :data:`WebhookVerificationError.REASONS`.
    """

    # The exhaustive set of reason codes. Same set and spellings as in
    # the Node (@legalize-dev/sdk) and Go SDKs so cross-language
    # metrics line up.
    REASONS: tuple[str, ...] = (
        "missing_header",
        "bad_timestamp",
        "timestamp_outside_tolerance",
        "no_valid_signature",
        "bad_signature",
    )

    def __init__(self, message: str = "verification failed", *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


# --- internal parsing ----------------------------------------------------


def _parse_error_body(
    data: Any, response: httpx.Response
) -> tuple[str | None, str, dict[str, Any]]:
    """Pull (code, message, extras) out of a server error body.

    Handles the three shapes documented in the module docstring. Always
    returns a message, defaulting to the HTTP reason phrase or the raw
    body when the server sent nothing parseable.
    """
    extras: dict[str, Any] = {}
    code: str | None = None
    message: str = ""

    if isinstance(data, dict):
        detail = data.get("detail", data)
        if isinstance(detail, dict):
            code = detail.get("error") or detail.get("code")
            message = detail.get("message") or detail.get("detail") or ""
            for key in ("retry_after", "limit", "upgrade_url"):
                if key in detail:
                    extras[key] = detail[key]
        elif isinstance(detail, list):
            # FastAPI 422 validation error: list of {loc,msg,type}
            extras["errors"] = detail
            if detail:
                message = detail[0].get("msg", "validation error")
            else:
                message = "validation error"
        elif isinstance(detail, str):
            message = detail

    # Populate retry_after from the header if the server did not put
    # it in the body. Accepts both delta-seconds and HTTP-date forms
    # (see parse_retry_after). Malformed headers yield None and are
    # intentionally dropped — the caller will fall back to its own
    # backoff policy rather than crash on a server bug.
    if "retry_after" not in extras:
        parsed = parse_retry_after(response.headers.get("retry-after"))
        if parsed is not None:
            extras["retry_after"] = parsed

    if not message:
        text = response.text.strip()
        message = text[:500] if text else f"HTTP {response.status_code}"

    return code, message, extras


def _pick_error_class(status: int, code: str | None) -> type[APIError]:
    if status == 400:
        return InvalidRequestError
    if status == 401:
        return AuthenticationError
    if status == 403:
        return ForbiddenError
    if status == 404:
        return NotFoundError
    if status == 422:
        return ValidationError
    if status == 429:
        return RateLimitError
    if status == 503:
        return ServiceUnavailableError
    if 500 <= status < 600:
        return ServerError
    return APIError


__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "ForbiddenError",
    "InvalidRequestError",
    "LegalizeError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ServiceUnavailableError",
    "ValidationError",
    "WebhookVerificationError",
]
