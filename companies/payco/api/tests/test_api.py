from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from payco.events import build_payment_succeeded, serialize  # noqa: E402
from payco.main import Settings, create_app  # noqa: E402
from payco.signing import sign  # noqa: E402

CUSTOMER = {"id": "cus_001", "name": "Ada Lovelace", "country": "GB"}


def test_event_shape_and_integer_cents() -> None:
    event = build_payment_succeeded("evt_0001", 1999, "EUR", CUSTOMER, created=1700000000)
    assert list(event) == ["id", "type", "created", "data"]
    assert event["data"]["amount_cents"] == 1999
    with pytest.raises(TypeError):
        build_payment_succeeded("evt_0001", 19.99, "EUR", CUSTOMER)  # type: ignore[arg-type]


def test_serialization_is_compact() -> None:
    body = serialize(build_payment_succeeded("evt_0001", 100, "EUR", CUSTOMER, created=1))
    assert b", " not in body and b": " not in body
    assert json.loads(body)["data"]["customer"]["name"] == "Ada Lovelace"


def test_signature_header() -> None:
    body = b'{"id":"evt_0001"}'
    header = sign(body, "s3cret", timestamp=1700000000)
    t, v1 = (part.split("=", 1)[1] for part in header.split(","))
    assert t == "1700000000"
    assert v1 == hmac.new(b"s3cret", b"1700000000." + body, hashlib.sha256).hexdigest()


def test_send_event_delivers_and_records(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def receiver(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(202)

    settings = Settings.__new__(Settings)
    settings.secret, settings.endpoint, settings.db_path, settings.timeout = "s3cret", "http://customer/webhook", str(tmp_path / "d.db"), 5
    client = TestClient(create_app(settings, httpx.MockTransport(receiver)))

    r = client.post("/admin/send-event", json={"customer": CUSTOMER, "amount_cents": 500})
    assert r.status_code == 200 and r.json() == {"event_id": "evt_0001", "response_status": 202, "error": None}
    r = client.post("/admin/send-event", json={"customer": CUSTOMER, "amount_cents": 700})
    assert r.json()["event_id"] == "evt_0002"

    sent = seen[0]
    t = sent.headers["PayCo-Signature"].split(",")[0][2:]
    expected = hmac.new(b"s3cret", f"{t}.".encode() + sent.content, hashlib.sha256).hexdigest()
    assert sent.headers["PayCo-Signature"].endswith(expected)
    rows = sqlite3.connect(settings.db_path).execute("SELECT event_id, body, response_status FROM deliveries").fetchall()
    assert rows[0] == ("evt_0001", sent.content, 202)


def test_float_amount_rejected(tmp_path: Path) -> None:
    settings = Settings.__new__(Settings)
    settings.secret, settings.endpoint, settings.db_path, settings.timeout = "s", "http://x/", str(tmp_path / "d.db"), 5
    client = TestClient(create_app(settings, httpx.MockTransport(lambda r: httpx.Response(202))))
    assert client.post("/admin/send-event", json={"customer": CUSTOMER, "amount_cents": 5.5}).status_code == 422
