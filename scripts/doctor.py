#!/usr/bin/env python3
"""`just doctor [0|1|2]`: are this machine's prerequisites in place for each way of trying Crosswire?

    Level 0  replay a recorded incident in the Incident Console     (Python 3.11+, Node 20+, just)
    Level 1  reproduce the bug and the fix, no agents               (+ Docker running, ports free)
    Level 2  the full live incident with Switch                     (+ a running Switch Console: see switch_setup.py)

Every failed check prints the exact fix. Read-only: it starts, installs and changes nothing.
"""
from __future__ import annotations

import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import toolpath  # noqa: E402

PORTS = {7001: "PayCo API", 7002: "ShopCo app", 7101: "PayCo evidence", 7102: "ShopCo evidence", 7400: "approver"}


def version(cmd: list[str]) -> tuple[int, ...] | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=toolpath.tool_env())
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", out.stdout + out.stderr)
    return tuple(int(x) for x in m.groups() if x is not None) if m else None


class Level:
    def __init__(self, n: int, title: str) -> None:
        self.n, self.failed = n, 0
        print(f"\nLevel {n}: {title}", flush=True)

    def __call__(self, label: str, ok: bool, fix: str = "", detail: str = "") -> bool:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{f' ({detail})' if detail else ''}", flush=True)
        if not ok:
            self.failed += 1
            print(f"        fix: {fix}", flush=True)
        return ok

    def verdict(self, how: str) -> bool:
        print(f"  -> Level {self.n} {'READY: ' + how if not self.failed else f'NOT READY ({self.failed} to fix)'}", flush=True)
        return not self.failed


def port_owner_is_ours(port: int) -> bool:
    """A port in use is fine when it's Crosswire's own container already running there."""
    r = subprocess.run(["docker", "ps", "--format", "{{.Ports}}"], capture_output=True, text=True, env=toolpath.tool_env())
    return r.returncode == 0 and f":{port}->" in r.stdout


def level0() -> bool:
    lv = Level(0, "replay a recorded incident (no Switch, Docker or Claude needed)")
    # the interpreter scripts/ensure-venv.sh would pick (the first of these on PATH), not the one running doctor
    pick = next((p for p in (shutil.which(n) for n in ("python3.12", "python3.13", "python3.11", "python3")) if p), None)
    pv = version([pick, "--version"]) if pick else None
    lv("Python 3.11+", bool(pv) and pv[:2] >= (3, 11), "install Python 3.11 or newer (python.org or `brew install python@3.12`)",
       f"{Path(pick).name} {'.'.join(map(str, pv))}" if pv else "not found")
    node = version(["node", "--version"]) if toolpath.resolve().get("node") else None
    lv("Node 20+", bool(node) and node[0] >= 20, "install Node 20 or newer (nodejs.org or `brew install node`)",
       ".".join(map(str, node)) if node else "not found")
    lv("npm", bool(toolpath.resolve().get("npm")), "npm comes with Node: reinstall Node 20+")
    lv("just", bool(toolpath.resolve().get("just")), "`brew install just` (or https://github.com/casey/just#installation)")
    lv("a recorded run to replay", (ROOT / "console/fixtures/demo-run.events.jsonl").exists(), "re-clone the repository")
    with socket.socket() as s:
        s.settimeout(0.5)
        busy = s.connect_ex(("127.0.0.1", 7300)) == 0
    lv("port 7300 available (or the Console already running there)", True, detail="in use: open http://127.0.0.1:7300" if busy else "free")
    return lv.verdict("`just console-replay`, then open http://127.0.0.1:7300")


def level1() -> bool:
    lv = Level(1, "reproduce the bug and the fix without agents (Docker)")
    lv("Docker installed", bool(toolpath.resolve().get("docker")), "install Docker Desktop (https://docs.docker.com/get-docker/)")
    up = subprocess.run(["docker", "info"], capture_output=True, text=True, env=toolpath.tool_env()).returncode == 0
    lv("Docker running", up, "start Docker Desktop and wait until it says it is running")
    compose = version(["docker", "compose", "version"]) if up else None
    lv("Docker Compose v2", bool(compose) and compose[0] >= 2, "update Docker Desktop (it includes Compose v2)",
       ".".join(map(str, compose)) if compose else "not found")
    lv("git", bool(toolpath.resolve().get("git")), "install git")
    for port, what in PORTS.items():
        with socket.socket() as s:
            s.settimeout(0.5)
            busy = s.connect_ex(("127.0.0.1", port)) == 0
        lv(f"port {port} available ({what})", not busy or (up and port_owner_is_ours(port)),
           f"something else listens on {port}: stop it (`lsof -nP -iTCP:{port} -sTCP:LISTEN` shows what)",
           "Crosswire's own container" if busy else "free")
    return lv.verdict("`just setup && just up && just simulate && just verify-bug && just verify-fixed`")


def level2() -> bool:
    print("\nLevel 2: the full live incident with Switch", flush=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts/switch_setup.py"), "--check"], cwd=ROOT)
    ok = r.returncode == 0
    print(f"  -> Level 2 {'READY: `just switch-setup`, then `just console` and press Run live incident' if ok else 'NOT READY'}")
    return ok


def main(argv: list[str]) -> int:
    levels = [int(a) for a in argv if a in ("0", "1", "2")] or [0, 1, 2]
    results = {n: (level0, level1, level2)[n]() for n in levels}
    print("\nSummary: " + " · ".join(f"Level {n} {'ready' if ok else 'not ready'}" for n, ok in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
