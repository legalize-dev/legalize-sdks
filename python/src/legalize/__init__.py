"""Legalize — official Python client for the Legalize API.

Typical usage::

    from legalize import Legalize

    client = Legalize(api_key="leg_...")
    for law in client.laws.iter(country="es"):
        print(law.id, law.title)

See https://legalize.dev/api for the API reference.
"""

from legalize._client import (
    DEFAULT_API_VERSION,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    AsyncLegalize,
    Legalize,
)
from legalize._errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    ForbiddenError,
    InvalidRequestError,
    LegalizeError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    ValidationError,
    WebhookVerificationError,
)
from legalize._retry import RetryPolicy
from legalize._version import __version__
from legalize.webhooks import Webhook, WebhookEvent

__all__ = [
    "DEFAULT_API_VERSION",
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AsyncLegalize",
    "AuthenticationError",
    "ForbiddenError",
    "InvalidRequestError",
    "Legalize",
    "LegalizeError",
    "NotFoundError",
    "RateLimitError",
    "RetryPolicy",
    "ServerError",
    "ServiceUnavailableError",
    "ValidationError",
    "Webhook",
    "WebhookEvent",
    "WebhookVerificationError",
    "__version__",
]
