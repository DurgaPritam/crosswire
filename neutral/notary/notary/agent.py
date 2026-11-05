"""The Notary's connection loop and behaviour.

One persistent connection id; SSE down, HTTP up; heartbeat every interval the server
names in connection_state; reconnect with Last-Event-ID and exponential backoff. Replies
are deduplicated by message id (persisted), so a restart or a replayed event never posts
twice.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import secrets
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from .client import ConnectionLost, SwitchClient, SwitchError
from .disclosures import Disclosure, DisclosureError, find_in, parse, side_of
from .report import HELP, UNKNOWN, comparison
from .sse import Frame, SSEParser

COMPARE = re.compile(r"\bcompare\s+(D-(?:PAY|SHOP)-\d+)\s+(D-(?:PAY|SHOP)-\d+)\b", re.I)
HELP_RE = re.compile(r"\bhelp\b", re.I)
SALT_RE = re.compile(r"\bsalt\s+(INC-\d{4})\b", re.I)
DOMAIN_EVENTS = {"message", "command", "room_join", "task_delegate", "task_accept", "task_update",
                 "task_finalise", "task_cancel"}
HANDLED_CAP = 500
READ_CONTEXT_PAGES = 5


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} notary: {msg}", file=sys.stderr, flush=True)


class State:
    """connection_id (reused forever), cursor, and the message ids already answered."""

    def __init__(self, path: Path) -> None:
        self.path = path
        data = json.loads(path.read_text()) if path.exists() else {}
        self.connection_id: str = data.get("connection_id") or str(uuid.uuid4())
        self.cursor: int | None = data.get("cursor")
        self.handled: list[str] = list(data.get("handled", []))
        self.salts: dict[str, str] = dict(data.get("salts", {}))
        self.salt_threads: dict[str, str] = dict(data.get("salt_threads", {}))  # incident -> thread it was issued in
        if not path.exists():
            self.save()

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"connection_id": self.connection_id, "cursor": self.cursor,
                                   "handled": self.handled[-HANDLED_CAP:], "salts": self.salts,
                                   "salt_threads": self.salt_threads}))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)


class Evicted(SwitchError):
    pass


class Notary:
    def __init__(self, client: SwitchClient, state: State, *,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep, max_backoff: float = 30.0) -> None:
        self.client = client
        self.state = state
        self.sleep = sleep
        self.max_backoff = max_backoff
        self.rooms: list[str] = []
        self.heartbeat_interval = 2.0
        self.current_room: str | None = None
        self.opens = 0
        self.evictions: list[float] = []
        self.pending_gap: dict[str, Any] | None = None
        self.stop = asyncio.Event()
        self.role = os.environ.get("NOTARY_ROLE", "notary")
        self.role_taken = False

    # ------------------------------------------------------------------ connection loop

    async def run(self, max_opens: int | None = None) -> None:
        attempt = 0
        while not self.stop.is_set() and (max_opens is None or self.opens < max_opens):
            self.opens += 1
            try:
                connected = await self._one_connection()
                attempt = 0 if connected else attempt + 1
            except Evicted as exc:
                now = time.monotonic()
                self.evictions = [t for t in self.evictions if now - t < 30] + [now]
                if len(self.evictions) >= 3:
                    raise SwitchError("evicted 3 times in 30s: another process is using this connection id. "
                                      "Run only one notary.") from exc
                log(f"evicted ({exc}); reopening")
                attempt += 1
            except ConnectionLost as exc:
                log(f"{exc}; reopening")
                attempt = 0  # docs: 404/409 mean reopen, not back off
                continue
            except (SwitchError, OSError, asyncio.TimeoutError, Exception) as exc:  # network blips, bad frames
                if isinstance(exc, (KeyboardInterrupt, asyncio.CancelledError)):
                    raise
                log(f"stream error: {type(exc).__name__}: {exc}")
                attempt += 1
            if self.stop.is_set():
                break
            delay = min(self.max_backoff, 2 ** max(0, attempt - 1)) * (0.8 + 0.4 * random.random()) if attempt else 0.2
            await self.sleep(delay)

    async def _one_connection(self) -> bool:
        """Open the stream, read until it ends. Returns True if connection_state arrived."""
        connected = asyncio.Event()
        reader = asyncio.create_task(self._read_stream(connected))
        beater = asyncio.create_task(self._heartbeat(connected))
        done, pending = await asyncio.wait({reader, beater}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        for t in pending:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        for t in done:
            exc = t.exception()
            if exc:
                raise exc
        return connected.is_set()

    async def _read_stream(self, connected: asyncio.Event) -> None:
        parser = SSEParser()
        async with self.client.stream(self.state.cursor) as resp:
            if resp.status_code in (404, 409):
                raise ConnectionLost(f"stream open refused ({resp.status_code}): {(await resp.aread())[:200]!r}")
            if resp.status_code != 200:
                raise SwitchError(f"stream open returned {resp.status_code}: {(await resp.aread())[:300]!r}")
            async for chunk in resp.aiter_text():
                for frame in parser.feed(chunk):
                    await self.handle_frame(frame, connected)
                    if self.stop.is_set():
                        return

    async def _heartbeat(self, connected: asyncio.Event) -> None:
        await connected.wait()
        while not self.stop.is_set():
            await self.sleep(self.heartbeat_interval)
            await self.client.beat(self.state.cursor)

    # ------------------------------------------------------------------ frames

    async def handle_frame(self, frame: Frame, connected: asyncio.Event) -> None:
        data = frame.data if isinstance(frame.data, dict) else {}
        kind = frame.event if frame.event != "message" or "type" not in data else data.get("type", frame.event)
        if kind == "connection_state":
            self.rooms = sorted(data.get("rooms") or [])
            if data.get("cursor") is not None:
                self.state.cursor = data["cursor"]
            self.heartbeat_interval = float(data.get("heartbeat_interval_seconds") or 2)
            self.state.save()
            connected.set()
            if not self.rooms:  # an all-scope connection claims nothing; fall back to the rooms we belong to
                self.rooms = await self.member_rooms()
            log(f"connected: {len(self.rooms)} room(s), cursor {self.state.cursor}, protocol {data.get('protocol')}")
            self.role_taken = False  # a lease can lapse while we were away: re-assert it on every connection
            await self.take_role()
        elif kind == "gap":
            self.pending_gap = data
            log(f"gap from {data.get('from_sequence')} resumed at {data.get('resumed_at')} ({data.get('reason')}); "
                "will re-read room history before answering")
        elif kind == "evicted":
            raise Evicted(str(data.get("reason", "evicted")))
        elif kind == "subscription_changed":
            self.rooms = sorted(data.get("rooms") or [])
            log(f"rooms now {self.rooms} ({data.get('reason')})")
            await self.take_role()
        elif kind == "room_released":
            if data.get("room_id") == self.current_room:
                self.current_room = None
        elif kind in DOMAIN_EVENTS:
            seq = data.get("sequence", frame.id)
            if kind == "message" and (data.get("payload") or {}).get("addressed"):
                try:
                    await self.on_message(data["room_id"], data["payload"])
                except (ConnectionLost, Evicted):
                    raise
                except SwitchError as exc:  # never let one message poison the stream (replayed forever)
                    log(f"could not answer {(data.get('payload') or {}).get('message_id')}: {exc}; skipping it")
                    mid = (data.get("payload") or {}).get("message_id")
                    if mid:
                        self.state.handled.append(mid)
            if seq is not None:
                self.state.cursor = max(int(seq), self.state.cursor or 0)
                self.state.save()

    async def member_rooms(self) -> list[str]:
        try:
            listed = await self.client.op("list_rooms") or []
        except SwitchError as exc:
            log(f"list_rooms failed: {exc}")
            return []
        rooms = listed.get("rooms", listed) if isinstance(listed, dict) else listed
        return sorted(r.get("id") or r.get("room_id") for r in rooms if isinstance(r, dict) and (r.get("id") or r.get("room_id")))

    async def take_role(self) -> None:
        """Hold the room's `notary` role (one role per agent across all rooms: the first room defining it)."""
        if self.role_taken or not self.role:
            return
        for room_id in self.rooms:
            try:
                ctx = await self.client.op("connect_to_room", room_id=room_id, include_general_instructions=False) or {}
                self.current_room = room_id
                names = {r.get("name") if isinstance(r, dict) else r for r in ctx.get("roles") or []}
                if self.role not in names:
                    continue
                await self.client.op("assume_role", role=self.role)
                self.role_taken = True
                log(f"took role {self.role} in {room_id}")
                return
            except SwitchError as exc:
                if "already" in str(exc).lower():
                    self.role_taken = True
                    return
                log(f"could not take role {self.role} in {room_id}: {exc}")

    # ------------------------------------------------------------------ behaviour

    async def on_message(self, room_id: str, payload: dict[str, Any]) -> None:
        message_id = payload.get("message_id")
        if message_id and message_id in self.state.handled:
            log(f"already answered {message_id}; skipping")
            return
        thread = payload.get("thread_id") or message_id
        reply = await self.respond(room_id, payload.get("body") or "", thread, payload.get("thread_id"))
        for attempt in (1, 2):  # always (re)bind the room first: a cached binding can be gone server-side
            await self.client.op("connect_to_room", room_id=room_id, include_general_instructions=False)
            self.current_room = room_id
            try:
                await self.client.op("post_message", body=reply, thread_id=thread)
                break
            except SwitchError as exc:
                if attempt == 2 or "connect_to_room" not in str(exc):
                    raise
                log(f"post failed ({exc}); reconnecting to the room and retrying once")
        self.pending_gap = None
        if message_id:
            self.state.handled.append(message_id)
            self.state.save()

    async def respond(self, room_id: str, body: str, thread: str | None = None, in_thread: str | None = None) -> str:
        m = COMPARE.search(body)
        if m:
            return await self.compare(room_id, m.group(1).upper(), m.group(2).upper(), thread)
        s = SALT_RE.search(body)
        if s:
            return self.salt(s.group(1).upper(), in_thread)
        if HELP_RE.search(body):
            return HELP
        return UNKNOWN

    def salt(self, incident: str, thread: str | None = None) -> str:
        """The incident salt: random (secrets), made once per incident and repeated if asked again.

        Incident ids restart (a new deployment, a rehearsal reset), so a request from a DIFFERENT incident thread for a
        known id gets a fresh salt: fingerprints must never be comparable across two incidents.
        """
        old_thread = self.state.salt_threads.get(incident)
        if incident in self.state.salts and thread and old_thread and old_thread != thread:
            del self.state.salts[incident]
        if thread:
            self.state.salt_threads[incident] = thread
        if incident not in self.state.salts:
            self.state.salts[incident] = f"{incident.lower()}-{secrets.token_hex(4)}"
            self.state.save()
        return (f"Salt for {incident}: `{self.state.salts[incident]}`. "
                "Every fingerprint in this incident must use exactly this salt.")

    async def compare(self, room_id: str, first: str, second: str, thread: str | None = None) -> str:
        sides = {side_of(first): first, side_of(second): second}
        if set(sides) != {"PAY", "SHOP"}:
            return f"I compare one PayCo and one ShopCo disclosure; got {first} and {second}."
        pay_id, shop_id = sides["PAY"], sides["SHOP"]
        found = await self.find_disclosures(room_id, {pay_id, shop_id}, thread)
        problems = []
        for d_id in (pay_id, shop_id):
            item = found.get(d_id)
            if item is None:
                problems.append(f"I can't find {d_id} in this room's history.")
            elif isinstance(item, DisclosureError):
                problems.append(f"{d_id} is malformed: {item}.")
        if problems:
            return " ".join(problems)
        try:
            return comparison(found[pay_id], found[shop_id])  # type: ignore[arg-type]
        except DisclosureError as exc:
            return f"Can't compare: {exc}."

    async def find_disclosures(self, room_id: str, wanted: set[str], thread: str | None = None) -> dict[str, Disclosure | DisclosureError]:
        """Latest occurrence of each wanted D-id, preferring the compare request's own thread.

        D-ids restart with every incident, so a same-named disclosure from an earlier, closed thread must not win
        over the one in this incident's thread: entries in `thread` are searched first, the rest of the room after.
        """
        found: dict[str, Disclosure | DisclosureError] = {}
        before: str | None = None
        for _ in range(READ_CONTEXT_PAGES):
            args: dict[str, Any] = {"room_id": room_id, "limit": 200}
            if before is not None:
                args["before"] = before
            ctx = await self.client.op("read_context", **args) or {}
            entries = [(thread is not None and (t.get("root") or {}).get("id") == thread, e)
                       for t in ctx.get("threads", []) for e in [t.get("root"), *t.get("replies", [])] if e]
            for _, entry in sorted(entries, key=lambda x: (x[0], x[1].get("timestamp") or 0), reverse=True):
                for d_id in find_in(entry.get("body") or ""):
                    if d_id in wanted and d_id not in found:
                        try:
                            found[d_id] = parse(entry["body"], d_id, entry.get("id"))
                        except DisclosureError as exc:
                            found[d_id] = exc
            if wanted <= found.keys() or not ctx.get("truncated") or ctx.get("oldest_timestamp") is None:
                break
            before = str(ctx["oldest_timestamp"])
        return found
