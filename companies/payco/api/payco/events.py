"""Event construction and wire serialization.

PayCo events are serialized once, compactly, and those exact bytes are what we sign and
send. See docs/webhooks.md.
"""

from __future__ import annotations

import json
import time
from typing import Any


def build_payment_succeeded(event_id: str, amount_cents: int, currency: str,
                            customer: dict[str, str], created: int | None = None) -> dict[str, Any]:
    if not isinstance(amount_cents, int) or isinstance(amount_cents, bool):
        raise TypeError("amount_cents must be an integer number of cents")
    return {
        "id": event_id,
        "type": "payment.succeeded",
        "created": int(time.time()) if created is None else created,
        "data": {
            "amount_cents": amount_cents,
            "currency": currency,
            "customer": {
                "id": customer["id"],
                "name": customer["name"],
                "country": customer["country"],
            },
        },
    }


def serialize(event: dict[str, Any]) -> bytes:
    """Compact JSON, the form we put on the wire."""
    return json.dumps(event, separators=(",", ":")).encode("utf-8")
