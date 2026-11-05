"""Read-only views of each agent's sessions: Switch's (Gateway GET) and the local Claude Code processes.

Never prints or stores a process command line: only PIDs, start times and the
working directory, the same discovery scripts/restart-agent.sh uses.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = {"payco-agent": "payco", "shopco-agent": "shopco", "mediator": "mediator"}
# Crosswire rooms each agent belongs to: Console runs (at most) one Claude Code session per room it's addressed in
ROOMS_PER_AGENT = {"payco-agent": 2, "shopco-agent": 2, "mediator": 1}
FOREIGN = ("spike-agent-a", "spike-agent-b", "switch-buddy-admin")   # must never be in the Crosswire rooms


def local_sessions(workspace: str) -> list[dict[str, Any]]:
    """Claude Code processes whose working directory is workspace/<workspace> (pid + start time only)."""
    target = (ROOT / "workspace" / workspace).resolve()
    out = []
    ps = subprocess.run(["ps", "-axo", "pid=,comm="], capture_output=True, text=True).stdout
    for line in ps.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2 or Path(parts[1].strip()).name != "claude":
            continue
        pid = parts[0]
        cwd = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True).stdout
        path = next((l[1:] for l in cwd.splitlines() if l.startswith("n")), "")
        if path and Path(path).resolve() == target:
            started = subprocess.run(["ps", "-o", "lstart=", "-p", pid], capture_output=True, text=True).stdout.strip()
            out.append({"pid": int(pid), "started": started})
    return out


def switch_sessions(gw: Any, agent_id: str) -> list[dict[str, Any]]:
    """Live sessions Switch reports for an agent (GET /gateway/agents/{id}: `sessions`)."""
    detail = gw.req("GET", f"/agents/{agent_id}")
    return [s for s in detail.get("sessions") or [] if s.get("state") == "live"]


def per_room_duplicates(sw: list[dict[str, Any]]) -> dict[str, int]:
    """Rooms in which Switch lists more than one live session for the agent (room name or id -> count)."""
    by: dict[str, int] = {}
    for s in sw:
        key = s.get("room_name") or s.get("room_id") or "(no room: controller)"
        by[key] = by.get(key, 0) + 1
    return {k: v for k, v in by.items() if v > 1}


def foreign_members(gw: Any, rooms: dict[str, str], names: dict[str, str]) -> list[str]:
    """`#room: agent` for every FOREIGN agent (or agent id we can't name) that is a member of a Crosswire room."""
    bad = []
    for key, rid in rooms.items():
        for aid in gw.req("GET", f"/rooms/{rid}").get("agent_ids") or []:
            name = names.get(aid)
            if name is None or name in FOREIGN:
                bad.append(f"#{key}: {name or 'unknown agent ' + aid[:8]}")
    return bad


class PeakSessions:
    """Samples local session counts during a run; reports each agent's peak (for the run transcript)."""

    def __init__(self) -> None:
        self.peak = {a: 0 for a in AGENTS}
        self.last = 0.0

    def sample(self, every: float = 30.0) -> None:
        if time.monotonic() - self.last < every:
            return
        self.last = time.monotonic()
        for agent, ws in AGENTS.items():
            self.peak[agent] = max(self.peak[agent], len(local_sessions(ws)))
