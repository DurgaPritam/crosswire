"""Read the incident's rooms through Switch, for the rehearsal grader (instead of the chat platform's API).

Uses the Incident Console's observer agent (a Switch protocol agent, member of all three rooms), on its own connection,
and only two read operations: `get_room_detail` (which members are agents) and `read_context` by room id (history,
paged, claims nothing). Anything else is refused before a request is sent, like the Console's own observer client.

    posts = switch_read.incident(since_ms)      # [(room name, mmlib.Post)], oldest first
"""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "neutral" / "notary"))
sys.path.insert(0, str(ROOT / "scripts"))
import mmlib  # noqa: E402
from notary.client import SwitchClient  # noqa: E402
from notary.sse import SSEParser  # noqa: E402

CREDENTIALS = ROOT / "console" / "server" / ".credentials.json"
ROOMS_FILE = ROOT / "switch" / "state" / "rooms.json"
READ_OPS = frozenset({"get_room_detail", "read_context"})
PAGE = 200


class ReadOnlyClient(SwitchClient):
    async def op(self, name: str, **args: Any) -> Any:
        if name not in READ_OPS:
            raise PermissionError(f"switch_read is read-only: refused Switch operation {name!r}")
        return await super().op(name, **args)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat(timespec="milliseconds")


def to_posts(room: str, threads: list[dict[str, Any]], agents: set[str], since_ms: int) -> list[tuple[str, mmlib.Post]]:
    """Switch messages as the grader's Post shape. from_bot = the sender is one of the room's agents (per Switch)."""
    out = []
    for th in threads:
        root = th.get("root") or {}
        for m in [root, *(th.get("replies") or [])]:
            if not m or m.get("kind", "message") != "message" or int(m.get("timestamp") or 0) < since_ms:
                continue
            who = m.get("sender_name") or ""
            out.append((room, mmlib.Post(str(m.get("id") or ""), room, str(m.get("sender") or ""), who, "",
                                         m.get("body") or "", "" if m is root else str(root.get("id") or ""),
                                         int(m.get("timestamp") or 0), False, False, who in agents)))
    return out


async def _read(since_ms: int) -> list[tuple[str, mmlib.Post]]:
    creds = json.loads(CREDENTIALS.read_text())
    rooms = json.loads(ROOMS_FILE.read_text())
    c = ReadOnlyClient(creds.get("bridge_url") or mmlib.load_env()["SWITCH_BRIDGE_URL"], creds["id"], creds["api_key"],
                       uuid.uuid4().hex)
    posts: list[tuple[str, mmlib.Post]] = []
    try:
        async with c.http.stream("GET", c.events_path(None), headers={"Accept": "text/event-stream"}) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Switch stream open returned {resp.status_code}")
            parser = SSEParser()
            async for chunk in resp.aiter_text():
                for f in parser.feed(chunk):
                    data = f.data if isinstance(f.data, dict) else {}
                    if (f.event if f.event != "message" or "type" not in data else data.get("type")) != "connection_state":
                        continue
                    for name, rid in rooms.items():
                        agents = set((await c.op("get_room_detail", room_id=rid) or {}).get("agent_names") or [])
                        threads: list[dict[str, Any]] = []
                        before = None
                        for _ in range(50):   # page backwards until the history predates the run (`before` is ISO-8601)
                            page = await c.op("read_context", room_id=rid, limit=PAGE, **({"before": before} if before else {})) or {}
                            threads += page.get("threads") or []
                            oldest = page.get("oldest_timestamp")
                            if not page.get("truncated") or not oldest or oldest < since_ms:
                                break
                            before = iso(oldest)
                        posts += to_posts(name, threads, agents, since_ms)
                    return sorted({(r, p.id): (r, p) for r, p in posts}.values(), key=lambda rp: rp[1].create_at)
    finally:
        await c.aclose()
    raise RuntimeError("the Switch stream closed before connection_state")


def incident(since_ms: int, timeout: float = 90) -> list[tuple[str, mmlib.Post]]:
    return asyncio.run(asyncio.wait_for(_read(since_ms), timeout))
