"""Historical source warnings survive typed sync and async resource reads."""

import httpx
import pytest


def payload(state):
    return {
        "law_id": "IE-1995-act-2",
        "sha": "abcdef1",
        "content_md": "Complete law text.",
        "date": "2023-07-03",
        "version_date": "2023-07-03",
        "citation": "Source snapshot; read its coverage warning.",
        "citation_url": "https://example.test/citation",
        "kind": "consolidated" if state == "point_in_time" else state,
        "text_state": state,
        "status": "partially_repealed",
        "in_force": None,
        "source_url": "https://example.test/official-version",
        "basis": "current_snapshot" if state == "current" else "recorded_on_or_before",
        "text_superseded": None if state == "current" else state == "as_enacted",
        "warning": "This snapshot does not establish historical wording.",
        "amended_by": [{"source_id": "IE-2021-act-4", "date": "2021-03-27"}],
        "source_notes": [{"type": None, "text": "Source's note", "refs": []}],
    }


@pytest.mark.parametrize("state", ["current", "as_enacted", "point_in_time", "future_state"])
@pytest.mark.parametrize("method", ["at_date", "at_commit"])
def test_historical_metadata_survives_sync_resources(client, handler, state, method):
    expected = payload(state)
    handler[0] = lambda request: httpx.Response(200, json=expected, request=request)
    argument = expected["date"] if method == "at_date" else expected["sha"]
    result = getattr(client.laws, method)("ie", expected["law_id"], argument)
    for field in expected.keys() - {"date", "version_date", "citation", "citation_url"}:
        assert result.model_dump()[field] == expected[field]
    assert result.kind == expected["kind"]
    assert result.warning == expected["warning"]
    assert result.status == expected["status"]
    assert result.source_url == expected["source_url"]
    assert result.in_force is None
    assert result.text_superseded == expected["text_superseded"]


@pytest.mark.parametrize("state", ["current", "as_enacted", "point_in_time", "future_state"])
@pytest.mark.parametrize("method", ["at_date", "at_commit"])
async def test_historical_metadata_survives_async_resources(aclient, handler, state, method):
    expected = payload(state)
    handler[0] = lambda request: httpx.Response(200, json=expected, request=request)
    argument = expected["date"] if method == "at_date" else expected["sha"]
    async with aclient:
        result = await getattr(aclient.laws, method)("ie", expected["law_id"], argument)
    for field in expected.keys() - {"date", "version_date", "citation", "citation_url"}:
        assert result.model_dump()[field] == expected[field]
    assert result.text_state == state
    assert result.warning == expected["warning"]
    assert result.in_force is None


def latest_payload():
    return {
        "id": "IE-2014-act-38",
        "country": "ie",
        "title": "Companies Act 2014",
        "law_type": "act",
        "text_state": "point_in_time",
        "kind": "incomplete",
        "warning": "The source omits a provision; consult the amending Act.",
        "content_md": "Available text.",
        "articles_indexed": False,
    }


def test_latest_source_warning_survives_sync_resource(client, handler):
    expected = latest_payload()
    handler[0] = lambda request: httpx.Response(200, json=expected, request=request)
    result = client.laws.retrieve("ie", expected["id"])
    assert result.kind == "incomplete"
    assert result.warning == expected["warning"]
    assert result.text_state == "point_in_time"


async def test_latest_source_warning_survives_async_resource(aclient, handler):
    expected = latest_payload()
    handler[0] = lambda request: httpx.Response(200, json=expected, request=request)
    async with aclient:
        result = await aclient.laws.retrieve("ie", expected["id"])
    assert result.kind == "incomplete"
    assert result.warning == expected["warning"]
    assert result.text_state == "point_in_time"
