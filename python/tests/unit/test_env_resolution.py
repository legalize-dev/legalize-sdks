"""Cross-SDK environment-variable contract (see ``sdk/ENVIRONMENT.md``).

Verifies that the Python client honors:

- ``LEGALIZE_API_KEY``       — required unless passed explicitly
- ``LEGALIZE_BASE_URL``      — overrides the default API URL
- ``LEGALIZE_API_VERSION``   — overrides the default API version

Precedence rules enforced here:

1. Explicit constructor argument wins over the environment.
2. Environment wins over the built-in default.
3. Empty-string env vars are treated as unset.

The same suite should exist (by name and intent) in every official
Legalize SDK so the contract stays in lockstep across languages.
"""

from __future__ import annotations

import pytest

from legalize import AsyncLegalize, AuthenticationError, Legalize
from legalize._client import (
    DEFAULT_API_VERSION,
    DEFAULT_BASE_URL,
    _resolve_api_version,
    _resolve_base_url,
)

ENV_VARS = ("LEGALIZE_API_KEY", "LEGALIZE_BASE_URL", "LEGALIZE_API_VERSION")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with the Legalize env namespace empty."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# ---- LEGALIZE_API_KEY ---------------------------------------------------


class TestApiKey:
    def test_missing_raises(self):
        with pytest.raises(AuthenticationError) as ei:
            Legalize()
        assert ei.value.code == "missing_api_key"

    def test_empty_string_treated_as_missing(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "")
        with pytest.raises(AuthenticationError) as ei:
            Legalize()
        assert ei.value.code == "missing_api_key"

    def test_env_provides_key(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_env_abc")
        c = Legalize()
        assert c._api_key == "leg_env_abc"
        c.close()

    def test_explicit_arg_wins(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_env_abc")
        c = Legalize(api_key="leg_arg_xyz")
        assert c._api_key == "leg_arg_xyz"
        c.close()

    def test_invalid_prefix_rejected_early(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "sk_wrong")
        with pytest.raises(AuthenticationError) as ei:
            Legalize()
        assert ei.value.code == "invalid_api_key"


# ---- LEGALIZE_BASE_URL --------------------------------------------------


class TestBaseUrl:
    def test_resolver_default_when_nothing_set(self):
        assert _resolve_base_url(None) == DEFAULT_BASE_URL

    def test_resolver_uses_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
        assert _resolve_base_url(None) == "https://staging.legalize.dev"

    def test_resolver_explicit_wins(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
        assert _resolve_base_url("https://other.example") == "https://other.example"

    def test_resolver_empty_env_falls_through(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_BASE_URL", "")
        assert _resolve_base_url(None) == DEFAULT_BASE_URL

    def test_client_honors_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_t")
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
        c = Legalize()
        assert c._base_url == "https://staging.legalize.dev"
        c.close()

    def test_client_strips_trailing_slash_from_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_t")
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev/")
        c = Legalize()
        assert c._base_url == "https://staging.legalize.dev"
        c.close()

    def test_client_explicit_arg_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_t")
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://staging.legalize.dev")
        c = Legalize(base_url="https://explicit.example")
        assert c._base_url == "https://explicit.example"
        c.close()


# ---- LEGALIZE_API_VERSION ----------------------------------------------


class TestApiVersion:
    def test_resolver_default_when_nothing_set(self):
        assert _resolve_api_version(None) == DEFAULT_API_VERSION

    def test_resolver_uses_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_VERSION", "v2")
        assert _resolve_api_version(None) == "v2"

    def test_resolver_explicit_wins(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_VERSION", "v2")
        assert _resolve_api_version("v99") == "v99"

    def test_resolver_empty_env_falls_through(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_VERSION", "")
        assert _resolve_api_version(None) == DEFAULT_API_VERSION

    def test_client_honors_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_t")
        monkeypatch.setenv("LEGALIZE_API_VERSION", "v42")
        c = Legalize()
        assert c._api_version == "v42"
        assert c._headers["Legalize-API-Version"] == "v42"
        c.close()

    def test_client_explicit_arg_wins_over_env(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_t")
        monkeypatch.setenv("LEGALIZE_API_VERSION", "v42")
        c = Legalize(api_version="v1")
        assert c._api_version == "v1"
        c.close()


# ---- Zero-config construction ------------------------------------------


class TestZeroConfig:
    """`Legalize()` with no args, only the environment. The canonical
    Kubernetes-pod use case."""

    def test_full_env_is_enough(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_prod_xyz")
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://api.internal.example")
        monkeypatch.setenv("LEGALIZE_API_VERSION", "v1")
        c = Legalize()
        assert c._api_key == "leg_prod_xyz"
        assert c._base_url == "https://api.internal.example"
        assert c._api_version == "v1"
        assert c._headers["Authorization"] == "Bearer leg_prod_xyz"
        assert c._headers["Legalize-API-Version"] == "v1"
        c.close()

    def test_only_api_key_is_enough(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_prod_xyz")
        c = Legalize()
        assert c._base_url == DEFAULT_BASE_URL
        assert c._api_version == DEFAULT_API_VERSION
        c.close()

    @pytest.mark.asyncio
    async def test_async_also_zero_config(self, monkeypatch):
        monkeypatch.setenv("LEGALIZE_API_KEY", "leg_prod_xyz")
        monkeypatch.setenv("LEGALIZE_BASE_URL", "https://api.internal.example")
        monkeypatch.setenv("LEGALIZE_API_VERSION", "v1")
        async with AsyncLegalize() as c:
            assert c._api_key == "leg_prod_xyz"
            assert c._base_url == "https://api.internal.example"
            assert c._api_version == "v1"
