"""Crosswire Incident Console server: event bus + SSE + recorder + live-incident runner + static web app.

    python -m crosswire_console              # live (observer + tailers), http://127.0.0.1:7300
    python -m crosswire_console --replay F   # replay-only (no Switch, Docker or Claude needed)

Endpoints: GET /api/health · GET /api/config · GET /api/events (SSE) · GET /api/replay?name=… · GET /api/replays
           POST /api/record {"name"} · POST /api/record/stop · POST /api/run · GET /api/run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .sources import ROOT, Observer, Tailer, fetch_record, log
import toolpath  # noqa: E402  (scripts/, on sys.path via .sources)

WEB = Path(os.environ.get("CONSOLE_WEB_DIR") or ROOT / "console/web/dist")  # CONSOLE_WEB_DIR: serve a snapshot build
FIXTURES = ROOT / "console/fixtures"
REHEARSALS = ROOT / "rehearsals"
LOCK = ROOT / ".tmp/rehearsal.lock"
PORT = int(os.environ.get("CONSOLE_PORT", "7300"))
NAME_RE = re.compile(r"^[\w.-]+$")


class Bus:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.seen: set[str] = set()
        self.cond = asyncio.Condition()
        self.recording: Path | None = None
        self.epoch = 0

    async def emit(self, ev: dict[str, Any]) -> None:
        key = f"{ev.get('id')}:{ev['kind']}:{ev.get('d_id', '')}:{ev.get('status', '')}"
        if key in self.seen and ev["kind"] != "guard_check":
            return
        self.seen.add(key)
        ev = {**ev, "seq": len(self.events)}
        self.events.append(ev)
        if self.recording:
            with self.recording.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev) + "\n")
        async with self.cond:
            self.cond.notify_all()

    async def reset(self) -> None:
        self.events, self.seen = [], set()
        self.epoch += 1
        async with self.cond:
            self.cond.notify_all()


class Runner:
    """'Run live incident': one scripts/rehearse.py run at a time (the same lock rehearse.py itself takes)."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None
        self.started: float | None = None
        self.log = ROOT / ".tmp/console-run.log"

    def busy(self) -> bool:
        if self.proc and self.proc.poll() is None:
            return True
        if LOCK.exists():
            try:
                os.kill(int(LOCK.read_text().split()[0]), 0)
                return True
            except (OSError, ValueError):
                return False
        return False

    def start(self) -> dict[str, Any]:
        if self.busy():
            return {"ok": False, "error": "a rehearsal is already running"}
        try:  # the console server isn't a login shell: resolve docker/just/... the same way rehearse.py does
            toolpath.require()
        except toolpath.ToolMissing as exc:
            return {"ok": False, "error": str(exc)}
        self.log.parent.mkdir(exist_ok=True)
        fh = self.log.open("w")
        self.proc = subprocess.Popen([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/rehearse.py"), "--runs", "1"],
                                     cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT, text=True,
                                     env={**toolpath.tool_env(), "PYTHONUNBUFFERED": "1"})
        self.started = time.time()
        return {"ok": True, "pid": self.proc.pid}

    def status(self) -> dict[str, Any]:
        tail = self.log.read_text().splitlines()[-6:] if self.log.exists() else []
        return {"running": self.busy(), "started": self.started,
                "exit": None if not self.proc or self.proc.poll() is None else self.proc.returncode, "log": tail}


def replay_files() -> list[str]:
    files = sorted(FIXTURES.glob("*.events.jsonl")) + sorted(REHEARSALS.glob("*.events.jsonl"))
    return list(dict.fromkeys(f.name for f in files))  # a fixture copy of a rehearsal is listed once (fixtures win)


def read_replay(name: str) -> list[dict[str, Any]] | None:
    if not NAME_RE.match(name):
        return None
    for d in (FIXTURES, REHEARSALS):
        f = d / name
        if f.exists():
            return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    return None


class Server:
    def __init__(self, live: bool) -> None:
        self.bus = Bus()
        self.runner = Runner()
        self.live = live
        self.observer: Observer | None = None
        self.gateway: Any = None
        self.shared_room: str | None = None
        self.t0 = time.time()

    async def setup_live(self) -> None:
        import mmlib
        import phase7
        env = mmlib.load_env()
        rooms = ROOT / "switch/state/rooms.json"
        if rooms.exists():
            self.shared_room = json.loads(rooms.read_text()).get("payco-shopco-shared")
        if env.get("SWITCH_ADMIN_EMAIL") and env.get("SWITCH_BRIDGE_URL"):
            try:
                # read-only: the Console only GETs the mediator's record; any write is refused before it is sent
                self.gateway = await asyncio.get_running_loop().run_in_executor(None, lambda: phase7.admin(env, read_only=True))
            except Exception as exc:  # noqa: BLE001
                log(f"gateway login failed: {exc}")
        self.observer = Observer(env.get("SWITCH_BRIDGE_URL", ""), self.bus.emit, self.on_record)
        asyncio.create_task(self.observer.run())
        asyncio.create_task(Tailer(self.bus.emit).run())

    async def on_record(self, incident: str) -> None:
        if not (self.gateway and self.shared_room):
            return
        rec = await fetch_record(self.gateway, self.shared_room, incident)
        if rec:
            await self.bus.emit({"id": f"rec-{incident}-{time.time_ns()}", "t": int(time.time() * 1000), "kind": "record_update",
                                 "lane": "shared", "who": "mediator", "incident": incident, "action": "content", **rec})

    def config(self) -> dict[str, Any]:
        configured = bool(self.live and self.observer and Observer.configured())
        return {"switch_configured": configured, "observer": self.observer.status if self.observer else "disabled",
                "replays": replay_files(), "default_replay": "demo-run.events.jsonl" if (FIXTURES / "demo-run.events.jsonl").exists() else (replay_files() or [None])[-1]}

    # ---------------------------------------------------------------- HTTP

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await reader.readuntil(b"\r\n\r\n")
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            writer.close()
            return
        lines = head.decode("latin-1").split("\r\n")
        method, target, _ = (lines[0].split(" ") + ["", ""])[:3]
        headers = {k.lower(): v.strip() for k, v in (l.split(":", 1) for l in lines[1:] if ":" in l)}
        body = await reader.readexactly(int(headers.get("content-length", "0") or 0)) if method == "POST" else b""
        url = urlparse(target)
        try:
            if url.path == "/api/events":
                return await self.sse(writer)
            status, payload = await self.route(method, url.path, parse_qs(url.query), body)
            if isinstance(payload, (bytes, bytearray)):
                ctype = mimetypes.guess_type(url.path)[0] or "text/html; charset=utf-8"
                await self.send(writer, status, payload, ctype)
            else:
                await self.send(writer, status, json.dumps(payload).encode(), "application/json")
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            if url.path != "/api/events":
                writer.close()

    async def send(self, writer: asyncio.StreamWriter, status: int, data: bytes, ctype: str) -> None:
        reason = {200: "OK", 400: "Bad Request", 404: "Not Found", 409: "Conflict"}.get(status, "OK")
        writer.write(f"HTTP/1.1 {status} {reason}\r\nContent-Type: {ctype}\r\nContent-Length: {len(data)}\r\n"
                     f"Cache-Control: no-store\r\nConnection: close\r\n\r\n".encode() + data)
        await writer.drain()

    async def route(self, method: str, path: str, q: dict[str, list[str]], body: bytes) -> tuple[int, Any]:
        if path == "/api/health":
            return 200, {"ok": True, "mode": "live" if self.live else "replay", "observer": self.observer.status if self.observer else "disabled",
                         "events_received": self.observer.events_received if self.observer else 0, "events": len(self.bus.events),
                         "recording": self.bus.recording.name if self.bus.recording else None, "uptime_s": int(time.time() - self.t0)}
        if path == "/api/config":
            return 200, self.config()
        if path == "/api/replays":
            return 200, replay_files()
        if path == "/api/replay":
            evs = read_replay((q.get("name") or [""])[0])
            return (200, evs) if evs is not None else (404, {"error": "no such recording"})
        if not self.live and method != "GET":  # Replay mode is strictly read-only: no recorder, no Run button
            return 405, {"ok": False, "error": "replay mode is read-only"}
        if path == "/api/record" and method == "POST":
            name = json.loads(body or b"{}").get("name", "")
            if not NAME_RE.match(name):
                return 400, {"error": "bad name"}
            await self.bus.reset()
            if self.observer:  # a new run: its incident id restarts (INC-0001 again), so forget the last one
                self.observer.incident = None
            REHEARSALS.mkdir(exist_ok=True)
            self.bus.recording = REHEARSALS / f"{name}.events.jsonl"
            self.bus.recording.write_text("")
            return 200, {"recording": self.bus.recording.name}
        if path == "/api/record/stop" and method == "POST":
            name = self.bus.recording.name if self.bus.recording else None
            self.bus.recording = None
            return 200, {"stopped": name}
        if path == "/api/tools":  # what the Run button's subprocess will find (no login shell)
            found = toolpath.resolve()
            return 200, {"ok": all(found[n] for n in toolpath.REQUIRED), "required": list(toolpath.REQUIRED),
                         "found": {n: bool(v) for n, v in found.items()}}
        if path == "/api/run":
            if method == "POST":
                if not self.config()["switch_configured"]:
                    return 409, {"ok": False, "error": "Switch is not configured on this machine"}
                res = self.runner.start()
                return (200 if res["ok"] else 409), res
            return 200, self.runner.status()
        f = (WEB / path.lstrip("/")).resolve() if path != "/" else WEB / "index.html"
        if not str(f).startswith(str(WEB.resolve())) or not f.is_file():
            f = WEB / "index.html"
        if not f.exists():
            return 404, {"error": "web app not built: cd console/web && npm run build"}
        return 200, f.read_bytes()

    async def sse(self, writer: asyncio.StreamWriter) -> None:
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-store\r\nConnection: keep-alive\r\n\r\n")
        sent, epoch = 0, self.bus.epoch
        try:
            while True:
                if epoch != self.bus.epoch:
                    writer.write(b"event: reset\ndata: {}\n\n")
                    sent, epoch = 0, self.bus.epoch
                for ev in self.bus.events[sent:]:
                    writer.write(f"event: cw\ndata: {json.dumps(ev)}\n\n".encode())
                sent = len(self.bus.events)
                writer.write(b": keepalive\n\n")
                await writer.drain()
                async with self.bus.cond:
                    try:
                        await asyncio.wait_for(self.bus.cond.wait(), timeout=15)
                    except asyncio.TimeoutError:
                        pass
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()


async def amain(args: argparse.Namespace) -> None:
    server = Server(live=not args.replay)
    if server.live:
        await server.setup_live()
    srv = await asyncio.start_server(server.handle, "127.0.0.1", PORT)
    log(f"Incident Console on http://127.0.0.1:{PORT}/ ({'live' if server.live else 'replay only'})")
    async with srv:
        await srv.serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--replay", action="store_true", help="replay only: no observer, no Switch needed")
    try:
        asyncio.run(amain(ap.parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
