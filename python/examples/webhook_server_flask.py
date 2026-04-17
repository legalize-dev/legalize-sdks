"""Minimal Flask webhook server that verifies Legalize signatures.

Install dependencies::

    pip install flask legalize

Run::

    LEGALIZE_WHSEC=whsec_... flask --app examples/webhook_server_flask run

Then register the endpoint URL in the Legalize dashboard and hit
"Send test event" — your server should print the event.
"""

from __future__ import annotations

import os

from flask import Flask, abort, request

from legalize import Webhook, WebhookVerificationError

app = Flask(__name__)
SECRET = os.environ["LEGALIZE_WHSEC"]


@app.post("/webhooks/legalize")
def incoming() -> tuple[str, int]:
    try:
        event = Webhook.verify(
            payload=request.get_data(),
            sig_header=request.headers.get("X-Legalize-Signature", ""),
            timestamp=request.headers.get("X-Legalize-Timestamp", ""),
            secret=SECRET,
        )
    except WebhookVerificationError:
        abort(400)

    print(f"[{event.type}] {event.id} {event.data}")

    if event.type == "law.updated":
        # React to law updates — enqueue a worker, update your DB, etc.
        pass

    return "", 204
