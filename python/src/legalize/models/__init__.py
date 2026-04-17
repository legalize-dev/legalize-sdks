"""Pydantic models for the Legalize API.

The models in ``_generated.py`` are auto-generated from the canonical
OpenAPI spec — do not edit by hand. Regenerate with::

    scripts/gen_models.sh

This module re-exports the public names so consumers import from
``legalize.models`` directly.
"""

from legalize.models._generated import (
    Commit,
    CommitsResponse,
    CountryInfo,
    HTTPValidationError,
    JurisdictionInfo,
    LawAtCommitResponse,
    LawDetail,
    LawMeta,
    LawSearchResult,
    PaginatedLaws,
    Reform,
    ReformsResponse,
    StatsResponse,
    ValidationError,
    WebhookEndpointCreate,
    WebhookEndpointUpdate,
)

__all__ = [
    "Commit",
    "CommitsResponse",
    "CountryInfo",
    "HTTPValidationError",
    "JurisdictionInfo",
    "LawAtCommitResponse",
    "LawDetail",
    "LawMeta",
    "LawSearchResult",
    "PaginatedLaws",
    "Reform",
    "ReformsResponse",
    "StatsResponse",
    "ValidationError",
    "WebhookEndpointCreate",
    "WebhookEndpointUpdate",
]
