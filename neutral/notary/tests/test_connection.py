"""Reconnect logic against a fake Switch bridge (httpx.MockTransport serving scripted SSE)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from conftest import pay_disclosure, shop_disclosure

from notary.agent import Notary, State
from notary.client import SwitchClient, SwitchError
from notary.report import HELP, UNKNOWN

AGENT = "agent-notary"
ROOM = "room-shared"


def sse(kind: str, data: dict[str, Any], seq: int | None = None) -> bytes:
    head = f"id: {seq}\n" if seq is not None else ""
    return f"{head}event: {kind}\ndata: {json.dumps(data)}\n\n".encode()


def state_frame(cursor: int = 10) -> bytes:
    return sse("connection_state", {"connection_id": "x", "agent_id": AGENT, "scope": "all", "filter": "addressed",
                                    "rooms": [ROOM], "cursor": cursor, "protocol": 1, "heartbeat_interval_seconds": 2})


def message(seq: int, body: str, mid: str, thread: str | None = None) -> bytes:
    return sse("message", {"type": "message", "room_id": ROOM, "bridge_id": None, "channel_type": None, "sequence": seq,
                           "payload": {"addressed": True, "sender": "@switch-agent-m:x", "sender_name": "mediator",
                                       "message_id": mid, "body": body, "timestamp": 1, "thread_id": thread,
                                       "attachments": []}}, seq)


class FakeSwitch:
    def __init__(self, streams: list[list[bytes]], beats: list[int] | None = None,
                 context: list[str] | None = None) -> None:
        self.streams = streams
        self.beats = beats or []
        self.context = context if context is not None else [pay_disclosure(), shop_disclosure()]
        self.opens: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []
        self.ops_called: list[str] = []
        self.hold = asyncio.Event()  # streams with "HOLD" stay open until set
        self.fail_posts = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == f"/agents/{AGENT}/ops":
            return httpx.Response(200, json={"operations": {n: {} for n in ("read_context", "post_message", "connect_to_room")}})
        if path == f"/agents/{AGENT}/connection/beat":
            code = self.beats.pop(0) if self.beats else 200
            return httpx.Response(code, json={"ok": code == 200})
        if path.startswith(f"/agents/{AGENT}/ops/"):
            name = path.rsplit("/", 1)[1]
            assert request.headers.get("X-Switch-Connection-Id"), "ops must carry the connection id"
            self.ops_called.append(name)
            args = json.loads(request.content)
            if name == "read_context":
                threads = [{"root": {"id": f"m{i}", "kind": "message", "sender": "x", "sender_name": "y", "body": b,
                                     "timestamp": i, "attachments": []}, "replies": []} for i, b in enumerate(self.context)]
                return httpx.Response(200, json={"result": {"threads": threads, "truncated": False, "oldest_timestamp": 0}})
            if name == "post_message":
                if self.fail_posts:
                    self.fail_posts -= 1
                    return httpx.Response(400, json={"detail": "Not connected to a room. Call connect_to_room first."})
                self.posts.append(args)
                return httpx.Response(200, json={"result": {"event_id": f"posted-{len(self.posts)}"}})
            if name == "connect_to_room":
                return httpx.Response(200, json={"result": {"room_id": args.get("room_id"), "roles": [{"name": "notary"}, {"name": "incident-commander"}]}})
            return httpx.Response(200, json={"result": {"room_id": args.get("room_id")}})
        if path == f"/agents/{AGENT}/events":
            self.opens.append({"params": dict(request.url.params), "last_event_id": request.headers.get("Last-Event-ID")})
            frames = self.streams.pop(0) if self.streams else []
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=self._body(frames))
        return httpx.Response(404)

    async def _body(self, frames: list[bytes]) -> Any:
        for f in frames:
            if f == b"HOLD":
                await self.hold.wait()
                continue
            yield f
            await asyncio.sleep(0)


async def no_sleep(_: float) -> None:
    await asyncio.sleep(0)


def make(fake: FakeSwitch, tmp: Path, state: State | None = None) -> tuple[Notary, State]:
    state = state or State(tmp / "state.json")
    client = SwitchClient("http://bridge.test", AGENT, "key", state.connection_id, transport=httpx.MockTransport(fake.handler))
    return Notary(client, state, sleep=no_sleep), state


def run(coro: Any) -> Any:
    return asyncio.run(asyncio.wait_for(coro, timeout=10))


def test_compare_reply_in_thread_then_reconnect_resumes_without_duplicates(tmp_path: Path) -> None:
    cmd = message(11, "@notary compare D-PAY-1 D-SHOP-1", "msg-11", thread="root-1")
    fake = FakeSwitch([[state_frame(10), cmd], [state_frame(11), cmd]])  # server replays msg-11 after the drop
    notary, state = make(fake, tmp_path)
    run(notary.run(max_opens=2))

    assert len(fake.posts) == 1, "replayed event must not produce a second reply"
    post = fake.posts[0]
    assert post["thread_id"] == "root-1"
    assert "| data.customer.name | 19 | 15 | +4 | no | yes/no |" in post["body"]
    assert "First difference: data.customer.name, delta +4 bytes." in post["body"]
    assert fake.ops_called.index("connect_to_room") < fake.ops_called.index("post_message")
    first, second = fake.opens
    assert first["params"]["connection_id"] == second["params"]["connection_id"] == state.connection_id
    assert first["params"]["start_from"] == "head" or first["last_event_id"] is not None
    assert second["last_event_id"] == "11" and "start_from" not in second["params"]
    for p in ("scope", "filter", "protocol", "protocol_accepts", "client"):
        assert p in first["params"]
    assert (first["params"]["scope"], first["params"]["filter"]) == ("all", "addressed")


def test_restart_reuses_connection_id_and_never_reanswers(tmp_path: Path) -> None:
    cmd = message(11, "@notary compare D-SHOP-1 D-PAY-1", "msg-11")  # reversed order is fine
    fake = FakeSwitch([[state_frame(10), cmd]])
    notary, state = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    assert len(fake.posts) == 1 and fake.posts[0]["thread_id"] == "msg-11"

    fake.streams = [[state_frame(10), cmd]]  # a fresh process; the server replays the same message
    restarted = State(tmp_path / "state.json")
    assert restarted.connection_id == state.connection_id and restarted.cursor == 11
    notary2, _ = make(fake, tmp_path, restarted)
    run(notary2.run(max_opens=1))
    assert len(fake.posts) == 1
    assert fake.opens[-1]["last_event_id"] == "11"


def test_heartbeat_404_reopens_without_backoff(tmp_path: Path) -> None:
    fake = FakeSwitch([[state_frame(), b"HOLD"], [state_frame()]], beats=[404])
    notary, _ = make(fake, tmp_path)
    delays: list[float] = []

    async def record(d: float) -> None:
        delays.append(d)
        await asyncio.sleep(0)

    notary.sleep = record
    run(notary.run(max_opens=2))
    assert len(fake.opens) == 2
    assert all(d <= 2 for d in delays), f"404 must reopen, not back off: {delays}"


def test_gap_is_noted_then_cleared_by_next_answer(tmp_path: Path) -> None:
    fake = FakeSwitch([[state_frame(), sse("gap", {"from_sequence": 3, "resumed_at": 9, "reason": "restart"}),
                        message(12, "@notary help", "msg-12")]])
    notary, _ = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    assert fake.posts[0]["body"] == HELP
    assert notary.pending_gap is None


def test_unknown_command_and_missing_disclosure(tmp_path: Path) -> None:
    fake = FakeSwitch([[state_frame(), message(12, "@notary what do you think?", "m-a"),
                        message(13, "@notary compare D-PAY-1 D-SHOP-9", "m-b")]])
    notary, _ = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    assert fake.posts[0]["body"] == UNKNOWN
    assert fake.posts[1]["body"] == "I can't find D-SHOP-9 in this room's history."


def test_unaddressed_messages_are_ignored_but_advance_cursor(tmp_path: Path) -> None:
    unaddressed = message(15, "compare D-PAY-1 D-SHOP-1", "m-x").replace(b'"addressed": true', b'"addressed": false')
    fake = FakeSwitch([[state_frame(), unaddressed]])
    notary, state = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    assert fake.posts == [] and state.cursor == 15


def test_repeated_eviction_stops_with_a_clear_error(tmp_path: Path) -> None:
    evicted = [state_frame(), sse("evicted", {"reason": "takeover"})]
    fake = FakeSwitch([list(evicted), list(evicted), list(evicted)])
    notary, _ = make(fake, tmp_path)
    with pytest.raises(SwitchError, match="another process"):
        run(notary.run(max_opens=5))


def test_state_file_is_private(tmp_path: Path) -> None:
    State(tmp_path / "s.json")
    assert (tmp_path / "s.json").stat().st_mode & 0o777 == 0o600


def test_reasserts_the_notary_role_on_every_connection(tmp_path: Path) -> None:
    fake = FakeSwitch([[state_frame()], [state_frame()]])
    notary, _ = make(fake, tmp_path)
    run(notary.run(max_opens=2))
    assert fake.ops_called.count("assume_role") == 2  # a lease can lapse while disconnected
    assert fake.ops_called.index("connect_to_room") < fake.ops_called.index("assume_role")


def test_takes_the_role_when_added_to_a_room_later(tmp_path: Path) -> None:
    empty = sse("connection_state", {"rooms": [], "cursor": 10, "heartbeat_interval_seconds": 2})
    added = sse("subscription_changed", {"rooms": [ROOM], "reason": "joined"})
    fake = FakeSwitch([[empty, added]])
    notary, _ = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    assert fake.ops_called.count("assume_role") == 1


def test_salt_is_random_per_incident_and_stable(tmp_path: Path) -> None:
    fake = FakeSwitch([[state_frame(), message(12, "@notary salt INC-0001", "s1"), message(13, "@notary salt inc-0001", "s2"),
                        message(14, "@notary salt INC-0002", "s3")]])
    notary, state = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    import re
    salts = [re.search(r"`(inc-\d{4}-[0-9a-f]{8})`", p["body"]).group(1) for p in fake.posts]
    assert salts[0] == salts[1] and salts[0].startswith("inc-0001-") and salts[2].startswith("inc-0002-")
    assert State(tmp_path / "state.json").salts["INC-0001"] == salts[0]


def test_lost_room_binding_reconnects_and_retries_once(tmp_path: Path) -> None:
    fake = FakeSwitch([[state_frame(), message(12, "@notary help", "m-1")]])
    fake.fail_posts = 1
    notary, _ = make(fake, tmp_path)
    run(notary.run(max_opens=1))
    assert [p["body"] for p in fake.posts] == [HELP]
    assert fake.ops_called.count("connect_to_room") >= 2


def test_an_unanswerable_message_does_not_loop_forever(tmp_path: Path) -> None:
    cmd = message(12, "@notary help", "m-1")
    fake = FakeSwitch([[state_frame(), cmd], [state_frame(), cmd]])
    fake.fail_posts = 99
    notary, state = make(fake, tmp_path)
    run(notary.run(max_opens=2))
    assert fake.posts == [] and state.cursor == 12 and "m-1" in state.handled
    assert len(fake.opens) == 2
