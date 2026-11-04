"""scripts/lib/render_settings.py: placeholders, validation, valid JSON."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
import render_settings as rs  # noqa: E402

TEMPLATE = '{"permissions": {"deny": ["Read({{OTHER_COMPANY_DIR}}/**)", "Read(~/.ssh/**)"]}, "x": "{{PROJECT_DIR}}"}'


def test_renders_all_placeholders() -> None:
    out = json.loads(rs.render(TEMPLATE, {"OTHER_COMPANY_DIR": "//ws/shopco", "PROJECT_DIR": "/ws/payco"}))
    assert out["permissions"]["deny"][0] == "Read(//ws/shopco/**)"
    assert out["x"] == "/ws/payco"


def test_missing_placeholder_fails() -> None:
    with pytest.raises(SystemExit, match="OTHER_COMPANY_DIR"):
        rs.render(TEMPLATE, {"PROJECT_DIR": "/ws/payco"})


def test_relative_value_fails() -> None:
    with pytest.raises(SystemExit, match="absolute"):
        rs.render(TEMPLATE, {"PROJECT_DIR": "ws/payco", "OTHER_COMPANY_DIR": "/x"})


def test_result_must_be_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        rs.render('{"a": {{PROJECT_DIR}}}', {"PROJECT_DIR": "/x"})


def test_cli_writes_file(tmp_path: Path) -> None:
    tpl = tmp_path / "t.json"
    tpl.write_text(TEMPLATE)
    out = tmp_path / "sub" / "settings.json"
    r = subprocess.run([sys.executable, str(ROOT / "scripts/lib/render_settings.py"), str(tpl), str(out),
                        "PROJECT_DIR=/a/", "OTHER_COMPANY_DIR=/b", "HOME=/h"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(out.read_text())["x"] == "/a"


def test_committed_templates_render(tmp_path: Path) -> None:
    """Every committed settings.template.json renders with setup.sh's placeholder set."""
    values = {k: f"/machine/{k.lower()}" for k in
              ("PROJECT_DIR", "OTHER_COMPANY_DIR", "PAYCO_DIR", "SHOPCO_DIR", "MEDIATOR_DIR", "WORKSPACE_DIR", "REPO_DIR", "HOME")}
    for tpl in ROOT.glob("*/*/.claude/settings.template.json"):
        text = tpl.read_text()
        assert "/Users/" not in text and "/home/" not in text, f"{tpl} contains an absolute home path"
        json.loads(rs.render(text, values))
