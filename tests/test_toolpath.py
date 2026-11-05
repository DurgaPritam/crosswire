"""scripts/toolpath.py: tools resolve with a launchd-style minimal PATH (the Console server isn't a login shell)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import toolpath  # noqa: E402

MINIMAL = "/usr/bin:/bin"


def test_search_path_keeps_inherited_entries_first_and_adds_known_dirs():
    p = toolpath.search_path("/custom/bin:/usr/bin").split(":")
    assert p[0] == "/custom/bin" and str(Path.home() / ".docker/bin") in p and p.count("/usr/bin") == 1


def test_tool_env_extends_path():
    env = toolpath.tool_env({"PATH": MINIMAL, "X": "1"})
    assert env["X"] == "1" and env["PATH"].startswith(MINIMAL) and "/opt/homebrew/bin" in env["PATH"]


def test_require_names_what_is_missing():
    with pytest.raises(toolpath.ToolMissing, match="definitely-not-a-tool-xyz"):
        toolpath.require("git", "definitely-not-a-tool-xyz", base=MINIMAL)


@pytest.mark.skipif(not shutil.which("docker", path=toolpath.search_path()), reason="docker not installed here")
def test_docker_resolves_from_a_minimal_path():
    """The run-4 failure: `docker` missing because the parent process had no ~/.docker/bin on PATH."""
    assert toolpath.which("docker", base=MINIMAL)
