"""ShopCo evidence tools: answers about ShopCo's private job queue and verify audit, never values.

Deliberately NO non-ASCII summary: ShopCo's realistic logs carry no names, so it can't see
that correlation. Only PayCo can.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from wirecheck import fingerprint

SALT_RE = re.compile(r"^[A-Za-z0-9._-]{4,64}$")
EVENT_RE = re.compile(r"^evt_[0-9]{1,8}$")

VERIFICATION_SPEC = (
    "ShopCo's webhook endpoint accepts PayCo's POST, parses the JSON body and puts the parsed event on an internal "
    "job queue, then waits briefly for the verdict (401 on a bad signature, otherwise 202). The raw request body "
    "is not stored. A background worker takes each job and verifies the PayCo-Signature header: it reads t and v1 "
    "from the header, serializes the queued event back to JSON, computes HMAC-SHA256 with the endpoint secret over "
    "t + '.' + that JSON, and compares the result with v1 in constant time. There is no timestamp tolerance check. "
    "Per PayCo's public docs, 'the signature is computed over the JSON payload'. The worker logs only the event id "
    "and ok/mismatch, and keeps an internal audit of the exact bytes it verified over."
)


def connect_ro(path: str) -> sqlite3.Connection:
    if not Path(path).exists():
        raise FileNotFoundError(f"job database not found at {path} (has any webhook arrived yet?)")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)


def _window(since_minutes: int) -> str:
    if not isinstance(since_minutes, int) or not 1 <= since_minutes <= 60 * 24 * 90:
        raise ValueError("since_minutes must be an integer between 1 and 129600")
    since = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
    return since.strftime("%Y-%m-%dT%H:%M:%S")


def list_signature_failures(db: sqlite3.Connection, since_minutes: int = 1440) -> list[dict[str, Any]]:
    rows = db.execute(
        """SELECT event_id, COALESCE(processed_at, created_at) FROM jobs
           WHERE status = 'failed' AND created_at >= ? ORDER BY id""", (_window(since_minutes),)).fetchall()
    return [{"event_id": e, "ts": ts} for e, ts in rows]


def get_verification_fingerprint(db: sqlite3.Connection, event_id: str, salt: str) -> dict[str, Any]:
    if not EVENT_RE.match(event_id or ""):
        raise ValueError("event_id must look like evt_0042")
    if not SALT_RE.match(salt or ""):
        raise ValueError("salt must be the incident salt (4-64 chars of A-Z a-z 0-9 . _ -)")
    row = db.execute("SELECT bytes FROM verify_audit WHERE event_id = ? ORDER BY id DESC LIMIT 1", (event_id,)).fetchone()
    if row is None:
        raise LookupError(f"no verification recorded for {event_id}")
    return fingerprint(row[0], salt, event_id)


def get_verification_spec() -> dict[str, Any]:
    return {"verifier": VERIFICATION_SPEC}
