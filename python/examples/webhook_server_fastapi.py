"""Minimal FastAPI webhook server with signature verification.

Install dependencies::

    pip install fastapi uvicorn legalize

Run::

    LEGALIZE_WHSEC=whsec_... uvicorn examples.webhook_server_fastapi:app
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException, Request

from legalize import Webhook, WebhookVerificationError

app = FastAPI()
SECRET = os.environ["LEGALIZE_WHSEC"]


@app.post("/webhooks/legalize", status_code=204)
async def incoming(
    request: Request,
    x_legalize_signature: str = Header(default=""),
    x_legalize_timestamp: str = Header(default=""),
) -> None:
    body = await request.body()
    try:
        event = Webhook.verify(
            payload=body,
            sig_header=x_legalize_signature,
            timestamp=x_legalize_timestamp,
            secret=SECRET,
        )
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400) from exc

    print(f"[{event.type}] {event.id}")
