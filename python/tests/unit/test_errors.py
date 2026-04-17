"""Error parsing + mapping from HTTP responses."""

from __future__ import annotations

import httpx
import pytest

from legalize import (
    APIError,
    AuthenticationError,
    ForbiddenError,
    InvalidRequestError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    ValidationError,
)


def _resp(status: int, body=None, headers=None, text: str | None = None) -> httpx.Response:
    req = httpx.Request("GET", "http://testserver/x")
    if text is not None:
        return httpx.Response(status, text=text, headers=headers or {}, request=req)
    return httpx.Response(status, json=body, headers=headers or {}, request=req)


class TestStatusMapping:
    @pytest.mark.parametrize(
        ("status", "cls"),
        [
            (400, InvalidRequestError),
            (401, AuthenticationError),
            (403, ForbiddenError),
            (404, NotFoundError),
            (422, ValidationError),
            (429, RateLimitError),
            (500, ServerError),
            (502, ServerError),
            (503, ServiceUnavailableError),
            (504, ServerError),
            (418, APIError),
        ],
    )
    def test_each_status(self, status, cls):
        err = APIError.from_response(_resp(status, {"detail": "oops"}))
        assert isinstance(err, cls)
        assert err.status_code == status


class TestStructuredDetail:
    def test_dict_detail_parses_code_and_extras(self):
        body = {
            "detail": {
                "error": "quota_exceeded",
                "message": "Monthly quota of 10000 exceeded.",
                "limit": 10000,
                "retry_after": 3600,
                "upgrade_url": "https://legalize.dev/pricing",
            }
        }
        err = APIError.from_response(_resp(429, body))
        assert isinstance(err, RateLimitError)
        assert err.code == "quota_exceeded"
        assert "Monthly quota" in err.message
        assert err.retry_after == 3600
        assert err.limit == 10000

    def test_string_detail(self):
        err = APIError.from_response(_resp(404, {"detail": "Law not found: xyz"}))
        assert isinstance(err, NotFoundError)
        assert err.message == "Law not found: xyz"

    def test_validation_error_list(self):
        body = {
            "detail": [
                {"loc": ["query", "year"], "msg": "value is not a valid integer", "type": "int"},
                {"loc": ["query", "page"], "msg": "must be >= 1", "type": "ge"},
            ]
        }
        err = APIError.from_response(_resp(422, body))
        assert isinstance(err, ValidationError)
        assert err.message == "value is not a valid integer"
        assert len(err.errors) == 2


class TestFallbacks:
    def test_empty_body_uses_status_line(self):
        err = APIError.from_response(_resp(500, text=""))
        assert err.message == "HTTP 500"
        assert err.data is None

    def test_non_json_body_kept_as_text(self):
        err = APIError.from_response(_resp(502, text="<html>bad gateway</html>"))
        assert "bad gateway" in err.message

    def test_retry_after_header_fallback(self):
        err = APIError.from_response(_resp(429, None, headers={"retry-after": "30"}))
        assert isinstance(err, RateLimitError)
        assert err.retry_after == 30

    def test_body_retry_after_wins(self):
        body = {"detail": {"error": "quota_exceeded", "message": "x", "retry_after": 7200}}
        err = APIError.from_response(_resp(429, body, headers={"retry-after": "30"}))
        assert err.retry_after == 7200  # body wins


class TestRequestId:
    def test_captures_request_id_header(self):
        err = APIError.from_response(
            _resp(500, {"detail": "boom"}, headers={"x-request-id": "req_abc"})
        )
        assert err.request_id == "req_abc"
        assert "request_id=req_abc" in str(err)


class TestStr:
    def test_includes_code_and_status(self):
        err = APIError.from_response(_resp(429, {"detail": {"error": "rate_limit", "message": "nope"}}))
        s = str(err)
        assert "HTTP 429" in s
        assert "rate_limit" in s
        assert "nope" in s
