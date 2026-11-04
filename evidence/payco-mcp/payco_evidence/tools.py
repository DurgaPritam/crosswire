"""PayCo evidence tools: answers about PayCo's private delivery log, never values.

Pure functions over a read-only SQLite connection, so they can be tested without MCP.
"""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wirecheck import ScanError, fingerprint, scan

SALT_RE = re.compile(r"^[A-Za-z0-9._-]{4,64}$")
EVENT_RE = re.compile(r"^evt_[0-9]{1,8}$")


def connect_ro(path: str) -> sqlite3.Connection:
    if not Path(path).exists():
        raise FileNotFoundError(f"delivery log not found at {path} (has anything been sent yet?)")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def _latest(db: sqlite3.Connection, since_minutes: int) -> list[tuple[str, bytes, int | None, str | None, float]]:
    """Latest delivery attempt per event inside the window."""
    since = time.time() - since_minutes * 60
    return db.execute(
        """SELECT d.event_id, d.body, d.response_status, d.error, d.ts FROM deliveries d
           JOIN (SELECT event_id, MAX(seq) AS seq FROM deliveries WHERE ts >= ? GROUP BY event_id) last
             ON d.seq = last.seq ORDER BY d.seq""", (since,)).fetchall()


def _failed(status: int | None, error: str | None) -> bool:
    return error is not None or status is None or not 200 <= status < 300


def _window(since_minutes: int) -> int:
    if not isinstance(since_minutes, int) or not 1 <= since_minutes <= 60 * 24 * 90:
        raise ValueError("since_minutes must be an integer between 1 and 129600")
    return since_minutes


def list_failed_deliveries(db: sqlite3.Connection, since_minutes: int = 1440) -> list[dict[str, Any]]:
    return [{"event_id": e, "status": status if error is None else f"error:{error}", "ts": _iso(ts)}
            for e, _body, status, error, ts in _latest(db, _window(since_minutes)) if _failed(status, error)]


def get_delivery_fingerprint(db: sqlite3.Connection, event_id: str, salt: str) -> dict[str, Any]:
    if not EVENT_RE.match(event_id or ""):
        raise ValueError("event_id must look like evt_0042")
    if not SALT_RE.match(salt or ""):
        raise ValueError("salt must be the incident salt (4-64 chars of A-Z a-z 0-9 . _ -)")
    row = db.execute("SELECT body FROM deliveries WHERE event_id = ? ORDER BY seq DESC LIMIT 1", (event_id,)).fetchone()
    if row is None:
        raise LookupError(f"no delivery recorded for {event_id}")
    return fingerprint(row[0], salt, event_id)


def summarize_failures(db: sqlite3.Connection, since_minutes: int = 1440) -> dict[str, Any]:
    """Failed vs ok deliveries, grouped by which fields carry non-ASCII text. No values."""
    groups: dict[str, dict[str, int]] = {}
    total = {"failed": 0, "ok": 0}
    for _e, body, status, error, _ts in _latest(db, _window(since_minutes)):
        outcome = "failed" if _failed(status, error) else "ok"
        total[outcome] += 1
        try:
            paths = sorted({leaf.path for leaf in scan(body) if leaf.non_ascii})
        except ScanError:
            paths = ["(unparseable body)"]
        keys = [f"{p} non_ascii" for p in paths] or ["no non_ascii fields"]
        for key in keys:
            groups.setdefault(key, {"failed": 0, "ok": 0})[outcome] += 1
    return {"window_minutes": since_minutes, "deliveries": total, "by_non_ascii_field": groups}


def get_signing_spec(docs_path: str | None) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "algorithm": "HMAC-SHA256, hex-encoded",
        "header": "PayCo-Signature: t=<unix seconds>,v1=<hex digest>",
        "signed_string": "<t> + '.' + <request body bytes exactly as PayCo sent them>",
        "body_serialization": "compact JSON (no spaces); non-ASCII characters are sent as \\uXXXX escapes",
        "secret": "the endpoint's signing secret, as UTF-8 bytes",
    }
    if docs_path and Path(docs_path).exists():
        text = Path(docs_path).read_text(encoding="utf-8")
        m = re.search(r"^## Verifying signatures\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        spec["public_docs_excerpt"] = (m.group(1).strip() if m else "(section not found)")
        spec["public_docs"] = "docs/webhooks.md"
    return spec
