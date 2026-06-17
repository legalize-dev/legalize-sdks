"""Unit tests for ``request_raw`` — the content-negotiation escape hatch.

Covers the sync and async clients, the ``format`` → ``Accept`` mapping,
the ``RawResponse`` helpers (``.xml()`` / ``.json()``), param/header
forwarding, and the error path.
"""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.unit

XML_BODY = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b"<response><id>BOE-A-1978-31229</id><title>Constitucion</title></response>"
)


def test_request_raw_defaults_to_xml(client, handler):
    captured: dict[str, str | None] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers.get("accept")
        return httpx.Response(
            200, content=XML_BODY, headers={"content-type": "application/xml; charset=utf-8"}
        )

    handler[0] = h
    res = client.request_raw("GET", "/api/v1/es/laws/BOE-A-1978-31229")
    assert captured["accept"] == "application/xml"
    assert res.status_code == 200
    assert res.content == XML_BODY
    assert res.text.startswith("<?xml")
    assert res.content_type == "application/xml; charset=utf-8"
    assert res.headers.get("content-type") == "application/xml; charset=utf-8"


def test_request_raw_xml_helper_parses(client, handler):
    handler[0] = lambda r: httpx.Response(
        200, content=XML_BODY, headers={"content-type": "application/xml"}
    )
    root = client.request_raw("GET", "/api/v1/es/laws/x").xml()
    assert root.tag == "response"
    assert root.find("id").text == "BOE-A-1978-31229"


def test_request_raw_json_format(client, handler):
    captured: dict[str, str | None] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers.get("accept")
        return httpx.Response(
            200, content=b'{"ok": true}', headers={"content-type": "application/json"}
        )

    handler[0] = h
    res = client.request_raw("GET", "/api/v1/countries", format="json")
    assert captured["accept"] == "application/json"
    assert res.json() == {"ok": True}


def test_request_raw_explicit_media_type(client, handler):
    captured: dict[str, str | None] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers.get("accept")
        return httpx.Response(200, content=b"<x/>", headers={"content-type": "text/xml"})

    handler[0] = h
    client.request_raw("GET", "/x", format="text/xml")
    assert captured["accept"] == "text/xml"


def test_request_raw_empty_format_defaults_xml(client, handler):
    captured: dict[str, str | None] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers.get("accept")
        return httpx.Response(200, content=b"<x/>")

    handler[0] = h
    client.request_raw("GET", "/x", format="")
    assert captured["accept"] == "application/xml"


def test_request_raw_forwards_params_and_extra_headers(client, handler):
    captured: dict[str, str | None] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["x_custom"] = request.headers.get("x-custom")
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, content=b"<x/>")

    handler[0] = h
    client.request_raw(
        "GET", "/api/v1/es/laws", params={"page": 2}, extra_headers={"X-Custom": "1"}
    )
    assert "page=2" in captured["url"]
    assert captured["x_custom"] == "1"
    # Default headers (Authorization, User-Agent, …) are still applied.
    assert captured["auth"].startswith("Bearer leg_")


def test_request_raw_raises_on_error(client, handler):
    from legalize import NotFoundError

    handler[0] = lambda r: httpx.Response(
        404,
        content=b"<response><error>not_found</error></response>",
        headers={"content-type": "application/xml"},
    )
    with pytest.raises(NotFoundError):
        client.request_raw("GET", "/api/v1/es/laws/none")
    # The failing response is still exposed for header inspection.
    assert client.last_response is not None
    assert client.last_response.status_code == 404


async def test_async_request_raw_xml(aclient, handler):
    captured: dict[str, str | None] = {}

    def h(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers.get("accept")
        captured["x_custom"] = request.headers.get("x-custom")
        return httpx.Response(
            200, content=XML_BODY, headers={"content-type": "application/xml; charset=utf-8"}
        )

    handler[0] = h
    res = await aclient.request_raw("GET", "/api/v1/es/laws/x", extra_headers={"X-Custom": "1"})
    assert captured["accept"] == "application/xml"
    assert captured["x_custom"] == "1"
    assert res.content_type == "application/xml; charset=utf-8"
    assert res.xml().tag == "response"
    await aclient.aclose()


async def test_async_request_raw_raises(aclient, handler):
    from legalize import NotFoundError

    handler[0] = lambda r: httpx.Response(404, content=b"<x/>")
    with pytest.raises(NotFoundError):
        await aclient.request_raw("GET", "/x")
    assert aclient.last_response is not None
    assert aclient.last_response.status_code == 404
    await aclient.aclose()
