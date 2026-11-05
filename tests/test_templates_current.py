"""The Switch templates are generated from the playbooks; they must be regenerated whenever a playbook changes."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_templates_match_playbooks() -> None:
    r = subprocess.run([sys.executable, str(ROOT / "scripts/build_templates.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_templates_carry_no_machine_paths() -> None:
    for name in ("crosswire-team.template.yaml", "crosswire.template.yaml"):
        text = (ROOT / "switch" / name).read_text()
        assert "/Users/" not in text and "/home/" not in text
