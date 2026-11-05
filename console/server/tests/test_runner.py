"""The "Run live incident" button's Runner: resolves tools without a login shell and fails loudly when one is missing.

The subprocess is stubbed: nothing is launched, Switch and Docker are not touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswire_console import app  # noqa: E402


class FakePopen:
    def __init__(self, cmd, **kw):
        self.cmd, self.env, self.pid = cmd, kw["env"], 4242

    def poll(self):
        return None


def runner(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "LOCK", tmp_path / "no.lock")
    r = app.Runner()
    r.log = tmp_path / "run.log"
    return r


def test_runner_gives_the_rehearsal_a_path_that_finds_docker(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")               # what a launchd/IDE-started server inherits
    launched = []
    monkeypatch.setattr(app.subprocess, "Popen", lambda cmd, **kw: launched.append(FakePopen(cmd, **kw)) or launched[-1])
    monkeypatch.setattr(app.toolpath, "require", lambda *a, **k: {})
    r = runner(tmp_path, monkeypatch)
    assert r.start()["ok"]
    path = launched[0].env["PATH"].split(":")
    assert str(Path.home() / ".docker/bin") in path and "/opt/homebrew/bin" in path
    assert launched[0].cmd[-3:] == [str(app.ROOT / "scripts/rehearse.py"), "--runs", "1"]


def test_runner_refuses_with_a_clear_message_when_a_tool_is_missing(tmp_path, monkeypatch):
    def missing(*a, **k):
        raise app.toolpath.ToolMissing("required tool(s) not found: docker")
    monkeypatch.setattr(app.toolpath, "require", missing)
    monkeypatch.setattr(app.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not launch")))
    res = runner(tmp_path, monkeypatch).start()
    assert res == {"ok": False, "error": "required tool(s) not found: docker"}
