"""Async resource coverage.

Mirrors tests/unit/test_resources.py for the AsyncLegalize client.
Kept compact — one test per method, just enough to exercise the async
request path and model parsing.
"""

from __future__ import annotations

import json as jsonlib

import httpx
import pytest

from legalize.models import (
    CommitsResponse,
    CountryInfo,
    JurisdictionInfo,
    LawAtCommitResponse,
    LawDetail,
    LawMeta,
    PaginatedLaws,
    ReformsResponse,
    StatsResponse,
)


def capture(handler_slot, *, status=200, body=None):
    received: dict[str, httpx.Request] = {}

    def h(req: httpx.Request) -> httpx.Response:
        received["request"] = req
        return httpx.Response(status, json=body if body is not None else {}, request=req)

    handler_slot[0] = h
    return received


LAW_META = {
    "id": "ley_organica_3_2018",
    "country": "es",
    "law_type": "ley_organica",
    "title": "Ley Orgánica 3/2018",
}


pytestmark = pytest.mark.asyncio


async def test_countries(aclient, handler):
    received = capture(handler, body=[{"country": "es", "count": 1}])
    out = await aclient.countries.list()
    assert received["request"].url.path == "/api/v1/countries"
    assert isinstance(out[0], CountryInfo)


async def test_jurisdictions(aclient, handler):
    received = capture(handler, body=[{"jurisdiction": "catalonia", "count": 5}])
    out = await aclient.jurisdictions.list("es")
    assert received["request"].url.path == "/api/v1/es/jurisdictions"
    assert isinstance(out[0], JurisdictionInfo)


async def test_law_types(aclient, handler):
    capture(handler, body=["ley", "real_decreto"])
    out = await aclient.law_types.list("es")
    assert out == ["ley", "real_decreto"]


async def test_laws_list(aclient, handler):
    received = capture(
        handler,
        body={
            "country": "es",
            "total": 1,
            "page": 1,
            "per_page": 50,
            "results": [dict(LAW_META)],
        },
    )
    out = await aclient.laws.list("es", law_type=["ley_organica"])
    assert isinstance(out, PaginatedLaws)
    assert dict(received["request"].url.params)["law_type"] == "ley_organica"


async def test_laws_search_requires_q(aclient):
    with pytest.raises(ValueError, match="q must be"):
        await aclient.laws.search("es", q="")


async def test_laws_search_works(aclient, handler):
    capture(
        handler,
        body={
            "country": "es",
            "total": 1,
            "page": 1,
            "per_page": 50,
            "results": [dict(LAW_META)],
            "query": "priv",
        },
    )
    out = await aclient.laws.search("es", q="priv")
    assert out.total == 1


async def test_laws_iter(aclient, handler):
    pages = [
        {
            "country": "es",
            "total": 3,
            "page": 1,
            "per_page": 2,
            "results": [{**LAW_META, "id": "a"}, {**LAW_META, "id": "b"}],
        },
        {
            "country": "es",
            "total": 3,
            "page": 2,
            "per_page": 2,
            "results": [{**LAW_META, "id": "c"}],
        },
    ]
    idx = [0]

    def h(req):
        resp = httpx.Response(200, json=pages[idx[0]], request=req)
        idx[0] += 1
        return resp

    handler[0] = h
    ids = [law.id async for law in aclient.laws.iter("es", per_page=2)]
    assert ids == ["a", "b", "c"]


async def test_laws_retrieve(aclient, handler):
    capture(handler, body={**LAW_META, "content_md": "body"})
    out = await aclient.laws.retrieve("es", "x")
    assert isinstance(out, LawDetail)


async def test_laws_meta(aclient, handler):
    capture(handler, body=LAW_META)
    out = await aclient.laws.meta("es", "x")
    assert isinstance(out, LawMeta)


async def test_laws_commits(aclient, handler):
    capture(
        handler,
        body={"law_id": "x", "commits": [{"sha": "a" * 7, "date": "2024-01-01", "message": "m"}]},
    )
    out = await aclient.laws.commits("es", "x")
    assert isinstance(out, CommitsResponse)


async def test_laws_at_commit(aclient, handler):
    capture(handler, body={"law_id": "x", "sha": "a" * 7, "content_md": "c"})
    out = await aclient.laws.at_commit("es", "x", "a" * 7)
    assert isinstance(out, LawAtCommitResponse)


async def test_reforms_list(aclient, handler):
    received = capture(
        handler,
        body={
            "law_id": "x",
            "total": 1,
            "offset": 0,
            "limit": 100,
            "reforms": [{"date": "2024-01-01", "source_id": "s"}],
        },
    )
    out = await aclient.reforms.list("es", "x")
    assert isinstance(out, ReformsResponse)
    q = dict(received["request"].url.params)
    assert q["limit"] == "100"


async def test_reforms_iter(aclient, handler):
    pages = [
        {
            "law_id": "x",
            "total": 3,
            "offset": 0,
            "limit": 2,
            "reforms": [{"date": "1", "source_id": "a"}, {"date": "2", "source_id": "b"}],
        },
        {
            "law_id": "x",
            "total": 3,
            "offset": 2,
            "limit": 2,
            "reforms": [{"date": "3", "source_id": "c"}],
        },
    ]
    idx = [0]

    def h(req):
        resp = httpx.Response(200, json=pages[idx[0]], request=req)
        idx[0] += 1
        return resp

    handler[0] = h
    ids = [r.source_id async for r in aclient.reforms.iter("es", "x", batch=2)]
    assert ids == ["a", "b", "c"]


async def test_stats(aclient, handler):
    received = capture(
        handler,
        body={
            "country": "es",
            "jurisdiction": None,
            "reform_activity_by_year": [],
            "most_reformed_laws": [],
            "law_types": [],
        },
    )
    out = await aclient.stats.retrieve("es", jurisdiction="cat")
    assert isinstance(out, StatsResponse)
    assert dict(received["request"].url.params)["jurisdiction"] == "cat"


async def test_webhooks_create(aclient, handler):
    received = capture(
        handler,
        body={"id": 1, "url": "u", "secret": "whsec_x", "event_types": ["law.updated"]},
    )
    out = await aclient.webhooks.create(url="u", event_types=["law.updated"])
    body = jsonlib.loads(received["request"].content)
    assert body["url"] == "u"
    assert out["id"] == 1


async def test_webhooks_list(aclient, handler):
    capture(handler, body=[{"id": 1}])
    out = await aclient.webhooks.list()
    assert out == [{"id": 1}]


async def test_webhooks_retrieve(aclient, handler):
    received = capture(handler, body={"id": 7})
    await aclient.webhooks.retrieve(7)
    assert received["request"].url.path == "/api/v1/webhooks/7"


async def test_webhooks_update(aclient, handler):
    received = capture(handler, body={"id": 7})
    await aclient.webhooks.update(7, enabled=True)
    body = jsonlib.loads(received["request"].content)
    assert body == {"enabled": True}


async def test_webhooks_delete(aclient, handler):
    received = capture(handler, body={"status": "deleted"})
    out = await aclient.webhooks.delete(7)
    assert received["request"].method == "DELETE"
    assert out == {"status": "deleted"}


async def test_webhooks_deliveries(aclient, handler):
    received = capture(handler, body={"deliveries": [], "total": 0})
    await aclient.webhooks.deliveries(7, page=3, status="success")
    q = dict(received["request"].url.params)
    assert q == {"page": "3", "status": "success"}


async def test_webhooks_deliveries_bad_status(aclient):
    with pytest.raises(ValueError, match="status"):
        await aclient.webhooks.deliveries(7, status="weird")


async def test_webhooks_retry(aclient, handler):
    received = capture(handler, body={"status": "success"})
    await aclient.webhooks.retry(7, 42)
    assert received["request"].url.path.endswith("/deliveries/42/retry")


async def test_webhooks_test(aclient, handler):
    received = capture(handler, body={"status": "success"})
    await aclient.webhooks.test(7)
    assert received["request"].url.path.endswith("/7/test")
