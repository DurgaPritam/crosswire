"""PayCo-Signature header: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>."""

from __future__ import annotations

import hashlib
import hmac
import time

HEADER = "PayCo-Signature"


def sign(body: bytes, secret: str, timestamp: int | None = None) -> str:
    t = int(time.time()) if timestamp is None else timestamp
    signed = f"{t}.".encode("ascii") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={t},v1={digest}"
