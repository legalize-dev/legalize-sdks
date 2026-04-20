"""Client construction, auth handling, defaults, context manager."""

from __future__ import annotations

import pytest

from legalize import AsyncLegalize, AuthenticationError, Legalize, RetryPolicy
from legalize._client import _build_headers, _clean_params, _resolve_retry_policy


class TestAPIKey:
    def test_rejects_missing_key(self, monkeypatch):
        monkeypatch.delenv("LEGALIZE_API_KEY", raising=False)
        with pytest.raises(AuthenticationError) as ei:
            Legalize()
        assert ei.value.code == "missing_api_key"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_env_12345")
        c = Legalize()
        assert c._api_key == "leg_env_12345"
        c.close()

    def test_rejects_bad_prefix(self):
        with pytest.raises(AuthenticationError) as ei:
            Legalize(api_key="sk-wrong-prefix")
        assert ei.value.code == "invalid_api_key"

    def test_explicit_arg_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_env_A")
        c = Legalize(api_key="leg_arg_B")
        assert c._api_key == "leg_arg_B"
        c.close()


class TestHeaders:
    def test_auth_and_user_agent(self):
        headers = _build_headers("leg_test", "v1", None)
        assert headers["Authorization"] == "Bearer leg_test"
        assert headers["Legalize-API-Version"] == "v1"
        assert headers["User-Agent"].startswith("legalize-python/")
        assert "python/" in headers["User-Agent"]

    def test_extra_overrides(self):
        headers = _build_headers("leg_test", "v1", {"User-Agent": "mybot/1"})
        assert headers["User-Agent"] == "mybot/1"


class TestCleanParams:
    def test_drops_none(self):
        assert _clean_params({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}

    def test_booleans_to_strings(self):
        assert _clean_params({"a": True, "b": False}) == {"a": "true", "b": "false"}

    def test_list_to_csv(self):
        assert _clean_params({"law_type": ["ley", "rd"]}) == {"law_type": "ley,rd"}

    def test_empty_list_dropped(self):
        assert _clean_params({"law_type": []}) == {}


class TestRetryResolution:
    def test_default(self):
        p = _resolve_retry_policy(None, None)
        assert isinstance(p, RetryPolicy)
        assert p.max_retries == 3  # DEFAULT_MAX_RETRIES

    def test_max_retries_shortcut(self):
        p = _resolve_retry_policy(None, 5)
        assert p.max_retries == 5

    def test_explicit_policy_wins(self):
        custom = RetryPolicy(max_retries=10)
        p = _resolve_retry_policy(custom, 2)
        assert p.max_retries == 10


class TestLifecycle:
    def test_context_manager(self):
        with Legalize(api_key="leg_cm") as c:
            assert not c._http.is_closed
        assert c._http.is_closed

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with AsyncLegalize(api_key="leg_cm") as c:
            assert not c._http.is_closed
        assert c._http.is_closed


class TestURLBuilding:
    def test_relative_path_gets_base_url(self):
        with Legalize(api_key="leg_t", base_url="https://example.test") as c:
            assert c._build_url("/api/v1/countries") == "https://example.test/api/v1/countries"

    def test_absolute_url_passes_through(self):
        with Legalize(api_key="leg_t", base_url="https://example.test") as c:
            assert c._build_url("https://other.test/x") == "https://other.test/x"

    def test_path_without_leading_slash(self):
        with Legalize(api_key="leg_t", base_url="https://ex.test") as c:
            assert c._build_url("api/v1/countries") == "https://ex.test/api/v1/countries"

    def test_trailing_slash_on_base_url(self):
        with Legalize(api_key="leg_t", base_url="https://ex.test/") as c:
            assert c._build_url("/api/v1") == "https://ex.test/api/v1"
