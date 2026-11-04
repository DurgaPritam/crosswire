"""Where the Notary keeps its credentials and state (both gitignored, mode 600)."""

from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]                 # neutral/notary
CREDENTIALS = Path(os.environ.get("NOTARY_CREDENTIALS", HERE / ".credentials.json"))
STATE = Path(os.environ.get("NOTARY_STATE", HERE / ".state.json"))


def bridge_url(creds: dict | None = None) -> str:
    url = os.environ.get("SWITCH_BRIDGE_URL") or (creds or {}).get("bridge_url")
    if not url:
        raise SystemExit("SWITCH_BRIDGE_URL is not set (the agent bridge base URL; probe it with GET /health)")
    return url.rstrip("/")


def load_credentials() -> dict:
    if not CREDENTIALS.exists():
        raise SystemExit(f"{CREDENTIALS} not found: register first with `python -m notary.register`")
    if CREDENTIALS.stat().st_mode & 0o077:
        raise SystemExit(f"{CREDENTIALS} is readable by others; run: chmod 600 {CREDENTIALS}")
    creds = json.loads(CREDENTIALS.read_text())
    if not creds.get("id") or not creds.get("api_key"):
        raise SystemExit(f"{CREDENTIALS} has no id/api_key")
    return creds
