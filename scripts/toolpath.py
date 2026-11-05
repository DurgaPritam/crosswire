"""Find the command-line tools Crosswire runs (docker, just, git, node, npm, uv) without relying on a login shell.

The Incident Console's server, IDE-launched scripts and launchd jobs don't get the PATH a terminal has, and Docker
Desktop installs its CLI in ~/.docker/bin, which only shells that ran Docker's profile snippet know about. Every
script that starts a subprocess uses `tool_env()` for that subprocess's environment, and `require()` fails loudly,
naming what's missing and where we looked.

    from toolpath import require, tool_env
    require("docker", "just")                       # raises ToolMissing with a clear message
    subprocess.run(["just", "up"], env=tool_env())   # PATH includes every known tool location
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

REQUIRED = ("docker", "just", "git", "node", "npm")   # what a rehearsal / live run needs
OPTIONAL = ("uv",)                                    # reported, not required


def extra_dirs() -> list[str]:
    home = Path.home()
    return [str(p) for p in (
        home / ".docker/bin",                                        # Docker Desktop's CLI (macOS)
        Path("/Applications/Docker.app/Contents/Resources/bin"),     # Docker Desktop, if ~/.docker/bin isn't linked
        Path("/opt/homebrew/bin"), Path("/usr/local/bin"),           # Homebrew (arm64, x86_64)
        home / ".local/bin", home / ".cargo/bin",                    # uv, just (cargo / standalone installers)
        Path("/usr/bin"), Path("/bin"),
    )]


def search_path(base: str | None = None) -> str:
    """The inherited PATH followed by the known tool directories, without duplicates."""
    seen: list[str] = []
    for d in (base if base is not None else os.environ.get("PATH", "")).split(os.pathsep) + extra_dirs():
        if d and d not in seen:
            seen.append(d)
    return os.pathsep.join(seen)


def which(name: str, base: str | None = None) -> str | None:
    return shutil.which(name, path=search_path(base))


def tool_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of the environment whose PATH finds every tool (use it for every subprocess)."""
    env = dict(os.environ if base is None else base)
    env["PATH"] = search_path(env.get("PATH", ""))
    return env


class ToolMissing(RuntimeError):
    pass


def resolve(names: tuple[str, ...] = REQUIRED + OPTIONAL, base: str | None = None) -> dict[str, str | None]:
    return {n: which(n, base) for n in names}


def require(*names: str, base: str | None = None) -> dict[str, str]:
    """Resolve each tool or raise ToolMissing naming every missing one and the directories searched."""
    found = resolve(names or REQUIRED, base)
    missing = [n for n, p in found.items() if not p]
    if missing:
        raise ToolMissing(f"required tool(s) not found: {', '.join(missing)}. Searched PATH plus "
                          f"{', '.join(extra_dirs()[:6])}. Install them (Docker Desktop for docker; `brew install just`) "
                          "or add their directory to PATH.")
    return {n: p for n, p in found.items() if p}
