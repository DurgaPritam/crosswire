#!/usr/bin/env python3
"""`just switch-setup`: from a running Switch Console to Crosswire's 3 agents, 3 rooms, roles, policies and claims.

    just switch-setup            # check the prerequisites, then run every phase7 step in order, then verify
    just switch-setup --check    # only the prerequisite checks (also used by `just doctor` for Level 2)

Every failed check prints the exact fix. What this can't do for you (and the README's Level 2 lists) is in MANUAL.
Never prints a password, an API key or a link code.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mmlib  # noqa: E402
import phase7  # noqa: E402
import toolpath  # noqa: E402

MANUAL = [
    "Install and open Switch Console (it starts the local Switch server and Mattermost, and registers this machine).",
    "In Switch Console: Admin → Status → turn Mattermost on (the bridge between Mattermost and Switch rooms).",
    "Create the Switch admin login, and put it in .env as SWITCH_ADMIN_EMAIL / SWITCH_ADMIN_PASSWORD.",
    "In Mattermost (System Console → Users), create the accounts `priya` and `sam` on the team Switch uses, and put "
    "their passwords in .env as MM_PRIYA_PASSWORD / MM_SAM_PASSWORD (only a Mattermost admin can create accounts).",
    "Optional, for the red-team suite: a third Mattermost account (MM_USER / MM_PASSWORD) that plays the outsider.",
    "Install Claude Code and log in (`claude` once in a terminal): Switch Console runs the three agents with it.",
]


class Checks:
    def __init__(self) -> None:
        self.failed = 0

    def __call__(self, label: str, ok: bool, fix: str = "", detail: str = "") -> bool:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{f' ({detail})' if detail else ''}", flush=True)
        if not ok:
            self.failed += 1
            if fix:
                print(f"        fix: {fix}", flush=True)
        return ok


def http_ok(url: str, timeout: float = 4) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200, f"HTTP {r.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError) as exc:
        return False, str(getattr(exc, "reason", exc))[:80]


def prerequisites(check: Checks) -> dict[str, str] | None:
    print("Level 2 prerequisites (a running Switch Console):", flush=True)
    env_file = ROOT / ".env"
    if not check(".env exists", env_file.exists(), "cp .env.example .env, then fill in the Switch and Mattermost logins"):
        return None
    e = mmlib.load_env()
    keys = ("SWITCH_ADMIN_EMAIL", "SWITCH_ADMIN_PASSWORD", "SWITCH_BRIDGE_URL", "MM_URL", "MM_PRIYA_PASSWORD", "MM_SAM_PASSWORD")
    missing = [k for k in keys if not e.get(k)]
    check(".env has the Switch and Mattermost logins", not missing, f"add {', '.join(missing)} to .env (see .env.example)",
          "missing: " + ", ".join(missing) if missing else "values never shown")
    tools = toolpath.resolve()
    for tool, fix in (("docker", "install Docker Desktop and start it"), ("just", "brew install just"),
                      ("git", "install git"), ("node", "install Node 20+")):
        check(f"{tool} found", bool(tools.get(tool)), fix)
    claude = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    check("Claude Code installed", Path(claude).exists() or bool(shutil.which("claude")),
          "install Claude Code (https://docs.anthropic.com/claude-code) and run `claude` once to log in")
    if missing:
        return None
    ok, why = http_ok(e["SWITCH_BRIDGE_URL"].rstrip("/") + "/health")
    if not check("Switch server reachable", ok, "open Switch Console (it starts the local Switch server); "
                 "SWITCH_BRIDGE_URL must be the agent bridge base URL", f"{e['SWITCH_BRIDGE_URL']}/health: {why}"):
        return None
    try:
        gw = phase7.admin(e, read_only=True)
    except (phase7.GatewayError, SystemExit) as exc:
        check("Switch admin login works", False, "check SWITCH_ADMIN_EMAIL / SWITCH_ADMIN_PASSWORD in .env", str(exc)[:100])
        return None
    check("Switch admin login works", True)
    bridges = phase7.items(gw.req("GET", "/collaborations"), "collaborations", "bridges")
    mm = [b for b in bridges if "mattermost" in json.dumps(b).lower()]
    check("Switch's Mattermost bridge is configured", bool(mm), "Switch Console: Admin → Status → turn Mattermost on")
    ok, why = http_ok(e["MM_URL"].rstrip("/") + "/api/v4/system/ping")
    check("Mattermost reachable", ok, "start Mattermost from Switch Console (Admin → Status)", f"{e['MM_URL']}: {why}")
    for name in ("priya", "sam"):
        try:
            mmlib.Mattermost(e["MM_URL"]).login(name, e[f"MM_{name.upper()}_PASSWORD"])
            check(f"Mattermost login for {name}", True)
        except mmlib.MMError as exc:
            check(f"Mattermost login for {name}", False, f"create the Mattermost account `{name}` (System Console → Users) "
                  f"and put its password in .env as MM_{name.upper()}_PASSWORD", str(exc)[:80])
    try:
        ctrl = phase7._controller(gw)
        check("this machine is registered with Switch (Switch Console running)", bool(ctrl))
    except phase7.GatewayError as exc:
        check("this machine is registered with Switch (Switch Console running)", False,
              "open Switch Console on this machine and sign in as the admin (it registers the machine)", str(exc)[:100])
    r = subprocess.run(["docker", "info"], capture_output=True, text=True, env=toolpath.tool_env())
    check("Docker is running", r.returncode == 0, "start Docker Desktop")
    return e


def verify(e: dict[str, str], check: Checks) -> None:
    print("\nResult (read back from Switch):", flush=True)
    gw = phase7.admin(e, read_only=True)
    names = {a.get("name") for a in phase7.items(gw.req("GET", "/agents"), "agents")}
    want = ["payco-agent", "shopco-agent", "mediator", "notary", "approver", "console-observer"]
    check("agents registered: " + ", ".join(want), all(w in names for w in want), "re-run `just switch-setup`",
          "missing: " + ", ".join(w for w in want if w not in names) if not all(w in names for w in want) else "")
    st = phase7.load_state()
    rooms = st.get("rooms") or {}
    check("rooms: #payco-internal, #shopco-internal, #payco-shopco-shared", len(rooms) == 3)
    for key, rid in rooms.items():
        members = set((gw.req("GET", f"/rooms/{rid}") or {}).get("agent_ids") or [])
        check(f"#{key} has its members", bool(members), detail=f"{len(members)} agents")
    smoke = st.get("smoke") or {}
    for label, ok in smoke.items():
        check(f"smoke: {label}", bool(ok), "see `scripts/phase7.py smoke` output above")
    check("approver policy saved", (ROOT / "switch/policies/approver.json").exists())


def main(argv: list[str]) -> int:
    check = Checks()
    e = prerequisites(check)
    if check.failed or e is None:
        print("\nNot ready for Level 2. Fix the items above, then re-run. Steps only you can do:")
        for i, m in enumerate(MANUAL, 1):
            print(f"  {i}. {m}")
        return 1
    if "--check" in argv:
        print("\nLevel 2 prerequisites: all present.")
        return 0
    if not (ROOT / "workspace" / "payco").exists():
        print("\nRunning `just setup` first (the agents' working directories)...", flush=True)
        subprocess.run(["just", "setup"], cwd=ROOT, check=True, env=toolpath.tool_env())
    print("\nWiring Crosswire into Switch (scripts/phase7.py all):", flush=True)
    r = subprocess.run([sys.executable, str(ROOT / "scripts/phase7.py"), "all"], cwd=ROOT, env={**os.environ, **toolpath.tool_env()})
    if r.returncode != 0:
        print("\nphase7 stopped with an error (above). Fix it and re-run `just switch-setup`: every step is idempotent.")
        return 1
    verify(e, check)
    if check.failed:
        return 1
    print("\nCrosswire is wired into Switch. Next: `just console`, then press \"Run live incident\" "
          "(or `.venv/bin/python scripts/rehearse.py --runs 1`).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
