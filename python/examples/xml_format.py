"""Fetch a law as XML via content negotiation.

The typed resource methods return JSON-parsed models; ``request_raw`` is
the escape hatch for callers whose pipeline speaks XML. It sets the
``Accept`` header for you and returns the body untouched.

Run:
    LEGALIZE_API_KEY=leg_... python examples/xml_format.py
"""

from __future__ import annotations

from legalize import Legalize


def main() -> None:
    with Legalize() as client:
        res = client.request_raw("GET", "/api/v1/es/laws/BOE-A-1978-31229")
        print("status:", res.status_code)
        print("content-type:", res.content_type)
        print(res.text[:400])

        # Parse it with the stdlib helper and pull a field out.
        root = res.xml()
        title = root.find("title")
        if title is not None:
            print("title:", title.text)


if __name__ == "__main__":
    main()
