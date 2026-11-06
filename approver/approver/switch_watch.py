"""The approver's Switch connection: everything it knows about the rooms comes through the agent protocol.

One `scope=all, filter=all` connection over the three Crosswire rooms (SSE down, HTTP up; the notary's client and
SSE parser, copied in at build time). From the events it keeps:

- each company agent's latest drafts in its private room (sender = that room's company agent, which the room's
  participant list shows as an agent);
- the notary's `Salt for INC-nnnn: ...` replies in the shared room (sender = notary), which name the current incident;
- approvals: `approve|deny D-…` from the room's owner, and only when Switch delivers the message as ADDRESSED to the
  approver. Addressing is decided by Switch on the server, from the approver's addressing policy (Priya in
  #payco-internal, Sam in #shopco-internal) matched against the platform accounts they claimed, so a message from
  anyone else is not addressed, whatever it says. The sender name is checked too, as a second line.

After a (re)connect it rebuilds drafts and salts from each room's history (`read_context`), so a restart mid-incident
loses nothing. Every signed or refused approval gets a one-line receipt in its thread.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:  # in the image: copied next to this file from neutral/notary/notary/
    from switch_client import ConnectionLost, SwitchClient, SwitchError  # type: ignore[import-not-found]
    from sse import SSEParser  # type: ignore[import-not-found]
except ImportError:  # in the repo (tests)
    sys.path.insert(0, str(HERE.parents[1] / "neutral" / "notary"))
    from notary.client import ConnectionLost, SwitchClient, SwitchError  # type: ignore[no-redef]
    from notary.sse import SSEParser  # type: ignore[no-redef]

import disclosure_canon as canon  # noqa: E402

CREDENTIALS = Path(os.environ.get("APPROVER_CREDENTIALS", "/run/approver/credentials.json"))
SHARED = "payco-shopco-shared"
COMPANY = {"payco-internal": ("priya", "payco-agent", "D-PAY"), "shopco-internal": ("sam", "shopco-agent", "D-SHOP")}
ROOMS = (*COMPANY, SHARED)
NOTARY = "notary"
APPROVE_RE = re.compile(r"\b(approve|deny)\s+(D-(?:PAY|SHOP)-\d+)\b", re.I)
DRAFT_RE = re.compile(r"^\s*(?:@[\w.-]+[\s,:]*)*DRAFT\s+(D-(?:PAY|SHOP)-\d+)\b")
SALT_POST_RE = re.compile(r"Salt for (INC-\d{4}):\s*`([^`\s]+)`")


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} approver: {msg}", flush=True)


class Rooms:
    """What the approver has learned from Switch about each room: drafts and members."""

    def __init__(self) -> None:
        self.ids: dict[str, str] = {}                       # room name -> id
        self.names: dict[str, str] = {}                     # room id -> name
        self.agents: dict[str, set[str]] = {}               # room name -> agent participants' names
        self.drafts: dict[str, list[dict[str, Any]]] = {r: [] for r in COMPANY}
        self.handled: set[str] = set()


def note_message(ap: Any, rooms: Rooms, room: str, p: dict[str, Any], live: bool) -> tuple[str, str] | None:
    """Apply one message (live event or history). Returns (thread_id, receipt) when an approval was decided."""
    body, who, mid = p.get("body") or "", p.get("sender_name") or "", p.get("message_id") or p.get("id") or ""
    ts = int(p.get("timestamp") or 0)
    if room == SHARED:
        m = SALT_POST_RE.search(body)
        if m and who == NOTARY and NOTARY in rooms.agents.get(SHARED, set()):
            ap.on_salt(m.group(1).upper(), m.group(2))
        return None
    if room not in COMPANY:
        return None
    human, agent, prefix = COMPANY[room]
    d = DRAFT_RE.match(body)
    if d and who == agent and agent in rooms.agents.get(room, set()) and canon.block(body, d.group(1)):
        rooms.drafts[room].append({"d_id": d.group(1), "message": body, "id": mid, "ts": ts})
        rooms.drafts[room] = rooms.drafts[room][-50:]
        return None
    a = APPROVE_RE.search(body)
    if not live or not a or mid in rooms.handled:
        return None                                         # history never approves: only a live, addressed message
    if not p.get("addressed") or who != human:
        if a:
            log(f"ignored `{a.group(0)}` from {who or '?'} in #{room}: "
                + ("not addressed to the approver (Switch decides who may address it)" if not p.get("addressed")
                   else f"sender is not {human}"))
        return None
    d_id = a.group(2).upper()
    if not d_id.startswith(prefix):
        return None
    rooms.handled.add(mid)
    drafts = [x for x in rooms.drafts[room] if x["d_id"] == d_id and x["ts"] <= ts]
    draft = max(drafts, key=lambda x: x["ts"]) if drafts else None
    outcome = ap.on_approval(room, a.group(1).lower(), d_id, {"create_at": ts, "id": mid, "user_id": p.get("sender")},
                             draft, human)
    return (p.get("thread_id") or mid, outcome)


class Watcher:
    def __init__(self, ap: Any, creds: dict[str, Any]) -> None:
        self.ap = ap
        url = os.environ.get("SWITCH_BRIDGE_URL") or creds["bridge_url"]
        self.client = SwitchClient(url, creds["id"], creds["api_key"], creds.get("connection_id") or str(uuid.uuid4()))
        self.rooms = Rooms()
        self.cursor: int | None = None
        self.beat_every = 2.0

    def path(self) -> str:   # the notary's stream, but every message in the covered rooms, not only addressed ones
        return self.client.events_path(self.cursor).replace("filter=addressed", "filter=all")

    async def learn_rooms(self) -> None:
        listed = await self.client.op("list_rooms") or []
        rows = listed.get("rooms", listed) if isinstance(listed, dict) else listed
        self.rooms.ids = {r["name"]: (r.get("room_id") or r.get("id")) for r in rows if r.get("name") in ROOMS}
        self.rooms.names = {v: k for k, v in self.rooms.ids.items()}
        for name, rid in self.rooms.ids.items():   # members and history, read by room id: nothing is claimed
            det = await self.client.op("get_room_detail", room_id=rid) or {}
            self.rooms.agents[name] = set(det.get("agent_names") or [])
            hist = await self.client.op("read_context", room_id=rid, limit=200) or {}
            msgs = []
            for th in hist.get("threads") or []:
                msgs += [th.get("root") or {}] + list(th.get("replies") or [])
            for m in sorted((x for x in msgs if x), key=lambda x: x.get("timestamp") or 0):
                note_message(self.ap, self.rooms, name, m, live=False)
        self.ap.rooms = set(self.rooms.ids)
        missing = sorted(set(ROOMS) - set(self.rooms.ids))
        log(f"watching {', '.join(sorted(self.rooms.ids))} through Switch"
            + (f"; NOT a member of {', '.join(missing)}" if missing else "")
            + f"; {sum(len(v) for v in self.rooms.drafts.values())} draft(s) from history; incident {self.ap.current}")

    async def receipt(self, room: str, thread: str, text: str) -> None:
        try:
            await self.client.op("connect_to_room", room_id=self.rooms.ids[room], include_general_instructions=False)
            await self.client.op("post_message", body=f"Approver: {text}", thread_id=thread)
        except SwitchError as exc:
            log(f"could not post the receipt in #{room}: {exc}")

    async def handle(self, data: dict[str, Any]) -> None:
        kind = data.get("type")
        if kind == "message":
            room = self.rooms.names.get(data.get("room_id", ""))
            if room:
                got = note_message(self.ap, self.rooms, room, data.get("payload") or {}, live=True)
                if got:
                    await self.receipt(room, *got)
        elif kind == "subscription_changed":   # our own receipts claim a room for a moment; nothing to re-read
            pass
        if data.get("sequence") is not None:
            self.cursor = max(int(data["sequence"]), self.cursor or 0)

    async def once(self) -> None:
        parser = SSEParser()
        headers = {"Accept": "text/event-stream", **({"Last-Event-ID": str(self.cursor)} if self.cursor is not None else {})}
        async with self.client.http.stream("GET", self.path(), headers=headers) as resp:
            if resp.status_code in (404, 409):
                raise ConnectionLost(f"stream open refused ({resp.status_code})")
            if resp.status_code != 200:
                raise SwitchError(f"stream open returned {resp.status_code}: {(await resp.aread())[:200]!r}")
            beater: asyncio.Task | None = None
            try:
                async for chunk in resp.aiter_text():
                    for f in parser.feed(chunk):
                        data = f.data if isinstance(f.data, dict) else {}
                        kind = f.event if f.event != "message" or "type" not in data else data.get("type")
                        if kind == "connection_state":
                            self.cursor = data.get("cursor", self.cursor)
                            self.beat_every = float(data.get("heartbeat_interval_seconds") or 2)
                            await self.learn_rooms()
                            self.ap.watching = True
                            if beater is None:
                                beater = asyncio.create_task(self.beat())
                        elif kind == "evicted":
                            raise ConnectionLost(f"evicted: {data.get('reason')}")
                        elif kind == "gap":
                            log(f"gap ({data.get('reason')}): re-reading room history")
                            await self.learn_rooms()
                        else:
                            await self.handle({**data, "type": kind})
            finally:
                self.ap.watching = False
                if beater:
                    beater.cancel()

    async def beat(self) -> None:
        while True:
            await asyncio.sleep(self.beat_every)
            await self.client.beat(self.cursor)

    async def run(self) -> None:
        await self.client.probe()
        await self.client.discover_ops()
        attempt = 0
        while True:
            try:
                await self.once()
                attempt = 0
            except ConnectionLost as exc:
                log(f"{exc}; reopening")
                attempt = 0
            except Exception as exc:  # noqa: BLE001  keep serving /health and /pubkey; nothing is signed meanwhile
                attempt += 1
                log(f"stream error ({type(exc).__name__}: {str(exc)[:160]}); retrying")
            await asyncio.sleep(min(30, 2 ** attempt) * (0.8 + 0.4 * random.random()) if attempt else 0.5)


def run_forever(ap: Any) -> None:
    if not CREDENTIALS.exists():
        log(f"no Switch credentials at {CREDENTIALS} (run `phase7.py approver`): serving, but not watching, so nothing "
            "gets signed")
        return
    creds = json.loads(CREDENTIALS.read_text())
    while True:
        try:
            asyncio.run(Watcher(ap, creds).run())
        except Exception as exc:  # noqa: BLE001
            ap.watching = False
            log(f"watcher stopped ({type(exc).__name__}: {str(exc)[:160]}); restarting in 10s")
            time.sleep(10)
