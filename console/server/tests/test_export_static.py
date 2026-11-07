"""The hosted Replay's export: replay-only config, every committed recording, the security data, and the real guard's
verdict on each sandbox preset (or none, when the workspaces aren't set up)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswire_console import breakit, export_static  # noqa: E402
from crosswire_console.app import FIXTURES  # noqa: E402


def test_export_writes_a_replay_only_site(tmp_path, monkeypatch):
    monkeypatch.setattr(export_static, "preset_verdicts", lambda: {"payco": {"x": {"allowed": False, "rules": []}}})
    assert export_static.main([str(tmp_path)]) == 0
    s = tmp_path / "static"
    cfg = json.loads((s / "config.json").read_text())
    assert cfg["switch_configured"] is False and cfg["default_replay"] in cfg["replays"]
    assert sorted(cfg["replays"]) == sorted(f.name for f in FIXTURES.glob("*.events.jsonl"))
    for name in cfg["replays"]:
        assert isinstance(json.loads((s / "replays" / f"{name}.json").read_text()), list)
    sec = json.loads((s / "security.json").read_text())
    assert {"scorecards", "attacks", "presets"} <= set(sec) and sec["presets"]["payco"]["x"]["allowed"] is False


def test_preset_verdicts_are_skipped_without_workspaces(tmp_path, monkeypatch):
    monkeypatch.setattr(breakit, "ROOT", tmp_path)   # no workspace/<company>/hooks here
    breakit._GUARDS.clear()
    assert export_static.preset_verdicts() == {}
