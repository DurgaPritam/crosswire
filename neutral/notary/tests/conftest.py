from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "neutral/notary")]

from wirecheck import fingerprint  # noqa: E402

SALT = "inc-0001-7f3a"


def event(name: str = "Chloé Martin") -> dict:
    return {"id": "evt_0042", "type": "payment.succeeded", "created": 1762300800,
            "data": {"amount_cents": 4200, "currency": "EUR",
                     "customer": {"id": "cus_0042", "name": name, "country": "FR"}}}


def payco_fp(salt: str = SALT, name: str = "Chloé Martin") -> dict:
    return fingerprint(json.dumps(event(name), separators=(",", ":")).encode(), salt, "evt_0042")


def shopco_fp(salt: str = SALT, name: str = "Chloé Martin") -> dict:
    return fingerprint(json.dumps(event(name), separators=(",", ":"), ensure_ascii=False).encode(), salt, "evt_0042")


def disclosure(d_id: str, owner: str, kind: str, fp: dict | None, salt: str = SALT, event_id: str = "evt_0042") -> str:
    body = f"[{d_id} · approved by @{owner}]\ntype: {kind}\nevent: {event_id}\nsalt: {salt}\n"
    if fp is not None:
        body += "```json\n" + json.dumps(fp, indent=1) + "\n```"
    return body


def pay_disclosure(**kw: object) -> str:
    return disclosure("D-PAY-1", "priya", "delivery_fingerprint", kw.pop("fp", payco_fp()), **kw)  # type: ignore[arg-type]


def shop_disclosure(**kw: object) -> str:
    return disclosure("D-SHOP-1", "sam", "verification_fingerprint", kw.pop("fp", shopco_fp()), **kw)  # type: ignore[arg-type]
