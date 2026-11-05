"""After `just setup`: every agent workspace has the canonical guards and a rendered, valid settings file."""

from __future__ import annotations

import filecmp
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WS = ROOT / "workspace"
AGENTS = {"payco": ["path_guard.py", "disclosure_guard.py"], "shopco": ["path_guard.py", "disclosure_guard.py"],
          "mediator": ["path_guard.py"]}

pytestmark = pytest.mark.skipif(not (WS / "payco").exists(), reason="run `just setup` first")


@pytest.mark.parametrize("agent", AGENTS)
def test_guards_are_canonical_copies(agent: str) -> None:
    for guard in AGENTS[agent]:
        assert filecmp.cmp(ROOT / "guards" / guard, WS / agent / "hooks" / guard, shallow=False), f"{agent}/{guard} drifted"


@pytest.mark.parametrize("agent", AGENTS)
def test_rendered_settings(agent: str) -> None:
    s = json.loads((WS / agent / ".claude" / "settings.json").read_text())
    assert "{{" not in json.dumps(s)
    deny = s["permissions"]["deny"]
    # Outside reads: deny rules + path_guard for file tools, the OS sandbox for Bash. blockReadsOutsideWorkingDirectories
    # is NOT used: with the sandbox on, it hangs Claude Code 2.1.299 at startup (bisected, see the threat model).
    assert "blockReadsOutsideWorkingDirectories" not in s["permissions"]
    assert s["permissions"]["blockWritesOutsideWorkingDirectories"] is True
    sb = s["sandbox"]
    assert sb["enabled"] and sb["failIfUnavailable"] and sb["allowUnsandboxedCommands"] is False
    assert f"{WS}/{agent}/hooks" in sb["filesystem"]["denyWrite"] and sb["network"]["allowedDomains"] == []
    for other in [a for a in ("payco", "shopco", "mediator") if a != agent]:
        assert f"{WS}/{other}" in sb["filesystem"]["denyRead"], f"{agent}'s sandbox must deny reading {other}"
    for tool in ("ps", "pgrep", "lsof", "launchctl", "sysctl", "curl", "ssh"):
        assert f"Bash({tool} *)" in deny
    others = [a for a in ("payco", "shopco", "mediator") if a != agent]
    for other in others:
        assert f"Read(/{WS}/{other}/**)" in deny, f"{agent} must deny reading {other}"
    assert f"Read(/{ROOT}/docs/**)" in deny and f"Read(/{ROOT}/reference-fixes/**)" in deny
    assert f"Read(/{ROOT}/console/**)" in deny and f"Read(/{ROOT}/approver/**)" in deny   # gap 10
    commands = [h["command"] for g in s["hooks"]["PreToolUse"] for h in g["hooks"]]
    assert any("path_guard.py" in c for c in commands)
    assert any("disclosure_guard.py" in c for c in commands) == (agent != "mediator")
    if agent == "mediator":
        assert any("--mediator" in c for c in commands)
        assert "Bash" in deny, "the mediator needs no shell: the notary hands out the salt"


@pytest.mark.parametrize("agent,port", [("payco", 7101), ("shopco", 7102)])
def test_mcp_json_points_at_own_evidence_server_only(agent: str, port: int) -> None:
    servers = json.loads((WS / agent / ".mcp.json").read_text())["mcpServers"]
    assert [s["url"] for s in servers.values()] == [f"http://127.0.0.1:{port}/mcp"]  # not localhost: Node resolves it to ::1
