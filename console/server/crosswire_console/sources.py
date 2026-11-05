"""Event sources: the observer agent (Switch protocol), disclosure/guard tailers, and the mediator's record.

The observer is a registered Switch agent that only listens (scope=all, filter=all), never posts, and whose
addressing policy admits nobody. It reuses the Notary's protocol client (neutral/notary/notary/client.py, sse.py).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "neutral/notary"), str(ROOT / "scripts")]

from notary.client import ConnectionLost, SwitchClient, SwitchError  # noqa: E402
from notary.sse import SSEParser  # noqa: E402

from .normalize import from_guard_log, from_message, parse_record  # noqa: E402

Emit = Callable[[dict[str, Any]], Awaitable[None]]
CREDENTIALS = ROOT / "console/server/.credentials.json"
STATE = ROOT / "console/server/.state.json"
ROOMS = ROOT / "switch/state/rooms.json"


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} console: {msg}", file=sys.stderr, flush=True)


class ReadOnlySwitchClient(SwitchClient):
    """The observer's protocol client: it may open its event stream and heartbeat, and nothing else. Every Switch
    operation (post_message, update_room_document, connect_to_room, ...) is refused here, before any request."""

    async def op(self, name: str, **args: Any) -> Any:  # noqa: ARG002
        raise PermissionError(f"the Console observer is read-only: refused Switch operation {name!r}")


class Observer:
    def __init__(self, bridge: str, emit: Emit, on_record: Callable[[str], Awaitable[None]]) -> None:
        self.bridge = bridge
        self.emit = emit
        self.on_record = on_record
        self.status = "disabled"
        self.events_received = 0
        self.incident: str | None = None
        self.room_names: dict[str, str] = {v: k for k, v in json.loads(ROOMS.read_text()).items()} if ROOMS.exists() else {}

    @staticmethod
    def configured() -> bool:
        return CREDENTIALS.exists() and ROOMS.exists()

    async def run(self) -> None:
        if not self.configured():
            log("observer not configured (console/server/.credentials.json or switch/state/rooms.json missing)")
            return
        creds = json.loads(CREDENTIALS.read_text())
        state = json.loads(STATE.read_text()) if STATE.exists() else {}
        conn = state.get("connection_id") or __import__("uuid").uuid4().hex
        STATE.write_text(json.dumps({"connection_id": conn}))
        client = ReadOnlySwitchClient(self.bridge, creds["id"], creds["api_key"], conn)
        backoff = 1.0
        while True:
            self.status = "connecting"
            try:
                await client.probe()
                await self._stream(client)
                backoff = 1.0
            except ConnectionLost as exc:
                log(f"observer: {exc}; reopening")
                backoff = 1.0
            except (SwitchError, OSError, Exception) as exc:  # noqa: BLE001 - keep listening through blips
                log(f"observer: {type(exc).__name__}: {exc}")
                backoff = min(30.0, backoff * 2)
            self.status = "disconnected"
            await asyncio.sleep(backoff)

    async def _stream(self, client: SwitchClient) -> None:
        parser = SSEParser()
        connected = asyncio.Event()
        interval = 2.0

        async def beat() -> None:
            await connected.wait()
            while True:
                await asyncio.sleep(interval)
                await client.beat(None)

        async def read() -> None:
            nonlocal interval
            path = client.events_path(None).replace("filter=addressed", "filter=all")
            async with client.http.stream("GET", path, headers={"Accept": "text/event-stream"}) as resp:
                if resp.status_code != 200:
                    raise SwitchError(f"observer stream open returned {resp.status_code}")
                async for chunk in resp.aiter_text():
                    for frame in parser.feed(chunk):
                        data = frame.data if isinstance(frame.data, dict) else {}
                        if frame.event == "connection_state":
                            interval = float(data.get("heartbeat_interval_seconds") or 2)
                            connected.set()
                            self.status = "connected"
                            log(f"observer connected ({len(data.get('rooms') or [])} rooms)")
                        elif frame.event == "evicted":
                            raise ConnectionLost("evicted")
                        elif frame.event == "message":
                            await self._message(data)

        tasks = [asyncio.create_task(read()), asyncio.create_task(beat())]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for t in pending:
            t.cancel()
        for t in done:
            if t.exception():
                raise t.exception()  # type: ignore[misc]

    async def _message(self, data: dict[str, Any]) -> None:
        p = data.get("payload") or {}
        room = self.room_names.get(data.get("room_id", ""))
        if room is None:
            return
        self.events_received += 1
        raw = {"id": p.get("message_id") or f"seq-{data.get('sequence')}", "t": int(p.get("timestamp") or time.time() * 1000),
               "room": room, "sender": p.get("sender_name") or p.get("sender") or "", "body": p.get("body") or "",
               "thread_id": p.get("thread_id")}
        for ev in from_message(raw, self.incident):
            if ev["kind"] == "incident_opened":
                self.incident = ev["incident"]
            await self.emit(ev)
            if ev["kind"] == "record_update" and ev.get("action") != "deleted":
                await self.on_record(ev["incident"])


class Tailer:
    """Polls each company's guard log (counts only; the log never holds text)."""

    def __init__(self, emit: Emit) -> None:
        self.emit = emit
        self.offsets: dict[str, int] = {}

    async def run(self) -> None:
        while True:
            for company in ("payco", "shopco"):
                f = ROOT / "workspace" / company / ".disclosures" / "guard.log.jsonl"
                if not f.exists():
                    self.offsets[company] = 0
                    continue
                lines = f.read_text(encoding="utf-8").splitlines()
                start = self.offsets.get(company, 0)
                if start > len(lines):  # the workspace was reset
                    start = 0
                for i, line in enumerate(lines[start:], start):
                    try:
                        entry = json.loads(line)
                        entry["t_ms"] = int(datetime.strptime(entry["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
                        await self.emit(from_guard_log(company, entry, i))
                    except (ValueError, KeyError):
                        continue
                self.offsets[company] = len(lines)
            await asyncio.sleep(1)


async def fetch_record(gateway: Any, shared_room_id: str, incident: str) -> dict[str, Any] | None:
    """The mediator's INC record via Gateway (admin). Returns status + hypotheses, or None."""
    loop = asyncio.get_running_loop()

    def get() -> dict[str, Any] | None:
        docs = gateway.req("GET", f"/rooms/{shared_room_id}/documents")
        docs = docs if isinstance(docs, list) else docs.get("documents", [])
        doc = next((d for d in docs if d.get("name") == incident), None)
        if not doc:
            return None
        detail = gateway.req("GET", f"/documents/{doc['id']}")
        content = detail.get("content") or (detail.get("document") or {}).get("content") or ""
        return parse_record(content)
    try:
        return await loop.run_in_executor(None, get)
    except Exception as exc:  # noqa: BLE001
        log(f"record fetch failed: {exc}")
        return None
