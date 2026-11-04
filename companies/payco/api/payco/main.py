"""PayCo API (webhook sender).

POST /admin/send-event   build a payment.succeeded event and deliver it to the
                         customer's webhook endpoint (internal admin tool)
GET  /health
"""

from __future__ import annotations

import os
import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field

from .deliveries import DeliveryLog
from .events import build_payment_succeeded, serialize
from .signing import HEADER, sign


class Customer(BaseModel):
    id: str
    name: str
    country: str = Field(min_length=2, max_length=2)


class SendEvent(BaseModel):
    customer: Customer
    amount_cents: int = Field(ge=0, strict=True)
    currency: str = Field(default="EUR", min_length=3, max_length=3)


class Settings:
    def __init__(self) -> None:
        self.secret = os.environ["WEBHOOK_SECRET"]
        self.endpoint = os.environ.get("CUSTOMER_WEBHOOK_URL", "http://shopco-app:3000/webhooks/payco")
        self.db_path = os.environ.get("PAYCO_DB", "/data/payco/deliveries.db")
        self.timeout = float(os.environ.get("DELIVERY_TIMEOUT_SECONDS", "10"))


def create_app(settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> FastAPI:
    settings = settings or Settings()
    log = DeliveryLog(settings.db_path)
    client = httpx.Client(timeout=settings.timeout, transport=transport)
    app = FastAPI(title="PayCo API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/admin/send-event")
    def send_event(req: SendEvent) -> dict[str, object]:
        event_id = log.next_event_id()
        event = build_payment_succeeded(event_id, req.amount_cents, req.currency, req.customer.model_dump())
        body = serialize(event)
        signature = sign(body, settings.secret)
        status: int | None = None
        error: str | None = None
        try:
            resp = client.post(settings.endpoint, content=body,
                               headers={"Content-Type": "application/json", HEADER: signature})
            status = resp.status_code
        except httpx.HTTPError as exc:
            error = type(exc).__name__
        log.record(event_id, body, signature, status, error)
        return {"event_id": event_id, "response_status": status, "error": error}

    return app


def app() -> FastAPI:  # uvicorn --factory payco.main:app
    return create_app()
