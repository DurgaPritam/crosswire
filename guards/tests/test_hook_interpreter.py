"""The hooks run on the system `python3` (3.9 on macOS), not the dev venv: the guards must work there too.
Found by red-team RT runs: glob.glob(root_dir=...) (3.10+) made path_guard block every Bash command with a glob."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

GUARDS = Path(__file__).resolve().parents[1]
SYSTEM_PY = shutil.which("python3", path="/usr/bin:/bin")
pytestmark = pytest.mark.skipif(not SYSTEM_PY, reason="no system python3")


@pytest.mark.parametrize("name", sorted(p.name for p in GUARDS.glob("*.py")))
def test_every_guard_compiles_on_the_hook_interpreter(name, tmp_path):
    r = subprocess.run([SYSTEM_PY, "-m", "py_compile", str(GUARDS / name)], capture_output=True, text=True,
                       env={"PYTHONPYCACHEPREFIX": str(tmp_path)})
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("command,allowed", [("ls src/*.py", True), ("ls ../../*", False), ("cat /etc/pass*", False)])
def test_path_guard_globs_on_the_hook_interpreter(tmp_path, command, allowed):
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "a.py").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    event = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(proj)}
    r = subprocess.run([SYSTEM_PY, str(GUARDS / "path_guard.py")], input=json.dumps(event), capture_output=True, text=True,
                       env={"CLAUDE_PROJECT_DIR": str(proj), "PATH": "/usr/bin:/bin"}, cwd=proj, timeout=30)
    assert (r.returncode == 0) is allowed, r.stderr
    assert "guard error" not in r.stderr
