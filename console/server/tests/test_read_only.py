"""The Console is read-only toward Switch: the observer can't call operations, the Gateway client can't write, and
Replay mode refuses every non-GET request."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswire_console import app, sources  # noqa: E402

import phase7  # noqa: E402  (scripts/ is on sys.path via sources)


def test_observer_client_refuses_every_operation():
    c = sources.ReadOnlySwitchClient("http://127.0.0.1:9", "agent", "key", "conn")
    for op in ("post_message", "update_room_document", "connect_to_room", "send_targeted_message"):
        with pytest.raises(PermissionError, match="read-only"):
            asyncio.run(c.op(op, body="x"))


def test_read_only_gateway_refuses_writes_before_sending(tmp_path, monkeypatch):
    monkeypatch.setattr(phase7, "AUDIT", tmp_path / "audit.jsonl")
    gw = phase7.Gateway("http://127.0.0.1:9", read_only=True)
    monkeypatch.setattr(gw, "_send", lambda *a, **k: pytest.fail("a write must not be sent"))
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        with pytest.raises(phase7.GatewayError, match="read-only"):
            gw.req(method, "/documents/x")
    assert (tmp_path / "audit.jsonl").read_text().count("refused-read-only") == 4


def test_replay_mode_refuses_non_get(monkeypatch):
    s = app.Server(live=False)
    for path in ("/api/run", "/api/record", "/api/record/stop"):
        status, body = asyncio.run(s.route("POST", path, {}, b"{}"))
        assert status == 405 and body["error"] == "replay mode is read-only"


def test_security_summary_is_get_only_data(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(app, "SCORECARDS", tmp_path)
    (tmp_path / "after.json").write_text(json.dumps({"label": "after", "ts": "t", "counts": {"blocked": 13},
        "results": [{"id": "RT01", "title": "x", "threat": "T4", "verdict": "blocked", "reasons": ["r"], "evidence": ["post"]}]}))
    s = app.Server(live=False)
    status, body = asyncio.run(s.route("GET", "/api/security", {}, b""))
    assert status == 200 and body["scorecards"][0]["results"][0]["verdict"] == "blocked"
    assert "evidence" not in body["scorecards"][0]["results"][0]      # posts' text stays in the scorecard files
    assert asyncio.run(s.route("POST", "/api/security", {}, b"{}"))[0] == 405
