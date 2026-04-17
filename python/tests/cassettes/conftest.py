"""VCR setup shared by all cassette tests.

The ``vcr_cassette`` fixture wraps a sync :class:`Legalize` client with
VCR. By default we replay offline and error on missing cassettes. Set
``VCR_RECORD=new`` to capture a cassette for the first time.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

try:
    import vcr as vcrpy
except ImportError:  # pragma: no cover
    vcrpy = None


CASSETTE_DIR = Path(__file__).parent / "cassettes"
CASSETTE_DIR.mkdir(exist_ok=True)


def _redact_request(request):
    # Replace the Authorization header before it's written to disk.
    if "Authorization" in request.headers:
        request.headers["Authorization"] = "Bearer leg_REDACTED"
    if "authorization" in request.headers:
        request.headers["authorization"] = "Bearer leg_REDACTED"
    return request


@pytest.fixture
def vcr_instance():
    if vcrpy is None:
        pytest.skip("vcrpy not installed")
    mode = os.environ.get("VCR_RECORD", "none")
    return vcrpy.VCR(
        cassette_library_dir=str(CASSETTE_DIR),
        record_mode=mode,
        match_on=["method", "scheme", "host", "path", "query"],
        filter_headers=["authorization"],
        before_record_request=_redact_request,
    )


@pytest.fixture
def vcr_cassette(request, vcr_instance) -> Iterator[object]:
    """Drop this fixture into a test to activate its cassette.

    The cassette file name defaults to the test node id.
    """
    cassette_name = f"{request.node.name}.yaml"
    with vcr_instance.use_cassette(cassette_name):
        yield cassette_name
