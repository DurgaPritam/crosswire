"""Gap 9: an evidence server with EVIDENCE_TOKEN set answers only requests that carry exactly that bearer token."""
from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("pkg", ["payco-mcp/payco_evidence", "shopco-mcp/shopco_evidence"])
def test_token_required(pkg, monkeypatch):
    sys.path.insert(0, str(ROOT / pkg.split("/")[0]))
    auth = importlib.import_module(pkg.split("/")[1] + ".auth")
    monkeypatch.setenv("EVIDENCE_TOKEN", "t0ken")

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    guarded = auth.require_token(app)

    def call(header: bytes | None) -> int:
        sent = []

        async def send(msg):
            sent.append(msg)

        headers = [(b"authorization", header)] if header is not None else []
        asyncio.run(guarded({"type": "http", "headers": headers}, None, send))
        return sent[0]["status"]

    assert call(None) == 401 and call(b"Bearer wrong") == 401 and call(b"t0ken") == 401
    assert call(b"Bearer t0ken") == 200
    monkeypatch.delenv("EVIDENCE_TOKEN")
    assert auth.require_token(app) is app            # no token configured: unchanged (preflight fails this case)


@pytest.mark.parametrize("pkg", ["payco-mcp/payco_evidence", "shopco-mcp/shopco_evidence"])
def test_leakage_budget_per_salt(pkg):
    sys.path.insert(0, str(ROOT / pkg.split("/")[0]))
    b = importlib.import_module(pkg.split("/")[1] + ".auth").Budget(limit=2)
    b.spend("inc-0001-aa", "evt_0001"); b.spend("inc-0001-aa", "evt_0002"); b.spend("inc-0001-aa", "evt_0001")
    with pytest.raises(PermissionError):
        b.spend("inc-0001-aa", "evt_0003")
    b.spend("inc-0002-bb", "evt_0003")               # a new incident salt has its own budget
