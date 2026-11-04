"""Delivery log: every webhook attempt, with the exact bytes sent.

Lives in PayCo's private data store (/data/payco/deliveries.db in production), never in
this repository.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS deliveries (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL,
    body            BLOB NOT NULL,
    signature       TEXT NOT NULL,
    response_status INTEGER,
    error           TEXT,
    ts              REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS deliveries_event ON deliveries(event_id);
"""


class DeliveryLog:
    def __init__(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self._conn() as db:
            db.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA journal_mode=DELETE")  # readers mount this volume read-only
        return conn

    def next_event_id(self) -> str:
        with self._conn() as db:
            (count,) = db.execute("SELECT COUNT(DISTINCT event_id) FROM deliveries").fetchone()
        return f"evt_{count + 1:04d}"

    def record(self, event_id: str, body: bytes, signature: str, response_status: int | None,
               error: str | None = None) -> None:
        with self._conn() as db:
            db.execute(
                "INSERT INTO deliveries (event_id, body, signature, response_status, error, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, body, signature, response_status, error, time.time()),
            )
