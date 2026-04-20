"""Contract tests against the filtered OpenAPI spec.

Two layers:

1. **Static spec validation** — parse the spec, confirm every operation
   loads into schemathesis without errors (catches dangling ``$ref``,
   unsupported types, malformed schema).
2. **SDK coverage** — every operation in the spec must be reachable via
   a resource method on the SDK client. Prevents shipping new endpoints
   that forget to add an SDK binding.

A third layer — fuzzing requests against a live server — runs in a
separate nightly CI job once ``staging.legalize.dev`` exists. Tracked
in the monorepo backlog.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import schemathesis

from legalize import AsyncLegalize, Legalize

SPEC_PATH = Path(__file__).resolve().parent.parent.parent.parent / "openapi-sdk.json"

if not SPEC_PATH.exists():
    pytest.skip(
        "openapi-sdk.json missing — run scripts/filter_openapi.py first",
        allow_module_level=True,
    )


@pytest.fixture(scope="module")
def schema() -> schemathesis.Schema:
    return schemathesis.openapi.from_dict(json.loads(SPEC_PATH.read_text()))


class TestSpecValidity:
    def test_spec_has_operations(self, schema):
        operations = list(schema.get_all_operations())
        assert len(operations) > 0, "spec has no operations"

    def test_every_operation_loads(self, schema):
        # schemathesis raises if an operation can't be parsed (broken ref,
        # unsupported schema, etc.). Just iterating is the test.
        for result in schema.get_all_operations():
            assert result is not None

    def test_expected_endpoints_present(self, schema):
        operations = list(schema.get_all_operations())
        pairs = {(op.ok().method.upper(), op.ok().path) for op in operations}

        required = {
            ("GET", "/api/health"),
            ("GET", "/api/v1/countries"),
            ("GET", "/api/v1/{country}/jurisdictions"),
            ("GET", "/api/v1/{country}/law-types"),
            ("GET", "/api/v1/{country}/laws"),
            ("GET", "/api/v1/{country}/laws/{law_id}"),
            ("GET", "/api/v1/{country}/laws/{law_id}/meta"),
            ("GET", "/api/v1/{country}/laws/{law_id}/reforms"),
            ("GET", "/api/v1/{country}/laws/{law_id}/commits"),
            ("GET", "/api/v1/{country}/laws/{law_id}/at/{sha}"),
            ("GET", "/api/v1/{country}/stats"),
            ("POST", "/api/v1/webhooks"),
            ("GET", "/api/v1/webhooks"),
            ("GET", "/api/v1/webhooks/{endpoint_id}"),
            ("PATCH", "/api/v1/webhooks/{endpoint_id}"),
            ("DELETE", "/api/v1/webhooks/{endpoint_id}"),
            ("GET", "/api/v1/webhooks/{endpoint_id}/deliveries"),
            ("POST", "/api/v1/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry"),
            ("POST", "/api/v1/webhooks/{endpoint_id}/test"),
        }
        missing = required - pairs
        assert not missing, f"spec is missing endpoints: {sorted(missing)}"

    def test_no_admin_or_dashboard_endpoints_leaked(self, schema):
        """Regression: the SDK spec must never re-introduce internal routes."""
        operations = list(schema.get_all_operations())
        paths = {op.ok().path for op in operations}
        forbidden = {p for p in paths if p.startswith(("/admin/", "/dashboard/", "/billing/"))}
        assert not forbidden, f"internal routes leaked into SDK spec: {forbidden}"


# ---- SDK surface coverage ---------------------------------------------


# Which resource.method on the sync client covers which (method, path).
# Keep this authoritative — adding an endpoint to the API without adding
# an SDK method will fail ``test_every_endpoint_has_sdk_binding``.
ENDPOINT_TO_SDK = {
    ("GET", "/api/v1/countries"): ("countries", "list"),
    ("GET", "/api/v1/{country}/jurisdictions"): ("jurisdictions", "list"),
    ("GET", "/api/v1/{country}/law-types"): ("law_types", "list"),
    ("GET", "/api/v1/{country}/laws"): ("laws", "list"),  # or .search() for q
    ("GET", "/api/v1/{country}/laws/{law_id}"): ("laws", "retrieve"),
    ("GET", "/api/v1/{country}/laws/{law_id}/meta"): ("laws", "meta"),
    ("GET", "/api/v1/{country}/laws/{law_id}/reforms"): ("reforms", "list"),
    ("GET", "/api/v1/{country}/laws/{law_id}/commits"): ("laws", "commits"),
    ("GET", "/api/v1/{country}/laws/{law_id}/at/{sha}"): ("laws", "at_commit"),
    ("GET", "/api/v1/{country}/stats"): ("stats", "retrieve"),
    ("POST", "/api/v1/webhooks"): ("webhooks", "create"),
    ("GET", "/api/v1/webhooks"): ("webhooks", "list"),
    ("GET", "/api/v1/webhooks/{endpoint_id}"): ("webhooks", "retrieve"),
    ("PATCH", "/api/v1/webhooks/{endpoint_id}"): ("webhooks", "update"),
    ("DELETE", "/api/v1/webhooks/{endpoint_id}"): ("webhooks", "delete"),
    ("GET", "/api/v1/webhooks/{endpoint_id}/deliveries"): ("webhooks", "deliveries"),
    ("POST", "/api/v1/webhooks/{endpoint_id}/deliveries/{delivery_id}/retry"): (
        "webhooks",
        "retry",
    ),
    ("POST", "/api/v1/webhooks/{endpoint_id}/test"): ("webhooks", "test"),
    # /api/health has no auth wrapper and no SDK binding (monitoring endpoint).
}


class TestSDKCoverage:
    def test_every_endpoint_has_sdk_binding(self, schema):
        operations = list(schema.get_all_operations())
        spec_endpoints = {
            (op.ok().method.upper(), op.ok().path)
            for op in operations
            if not op.ok().path == "/api/health"
        }
        missing = spec_endpoints - ENDPOINT_TO_SDK.keys()
        assert not missing, f"SDK has no binding for: {sorted(missing)}"

    @pytest.mark.parametrize(
        ("resource", "method"),
        sorted(set(ENDPOINT_TO_SDK.values())),
    )
    def test_sync_methods_are_callable(self, resource, method):
        with Legalize(api_key="leg_test", base_url="http://x") as client:
            r = getattr(client, resource)
            m = getattr(r, method)
            assert callable(m)

    @pytest.mark.parametrize(
        ("resource", "method"),
        sorted(set(ENDPOINT_TO_SDK.values())),
    )
    def test_async_methods_are_callable(self, resource, method):
        client = AsyncLegalize(api_key="leg_test", base_url="http://x")
        r = getattr(client, resource)
        m = getattr(r, method)
        assert callable(m)


@pytest.mark.integration
@pytest.mark.skip(reason="requires staging.legalize.dev; see monorepo backlog #17")
def test_live_fuzz_against_staging():
    """Placeholder for nightly contract fuzz against the real API.

    Run manually once STAGING_URL + STAGING_KEY are configured::

        STAGING_URL=https://staging.legalize.dev \\
        STAGING_KEY=leg_staging_xxx \\
        pytest tests/contract -m integration
    """
