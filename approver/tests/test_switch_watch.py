"""The approver's Switch watcher: what counts as a draft, a salt and an approval (switch_watch.note_message)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "guards"))
sys.path.insert(0, str(ROOT / "approver" / "approver"))
pytest.importorskip("httpx")
import switch_watch as sw  # noqa: E402

BLOCK = ("DRAFT D-PAY-3: fingerprint\n[D-PAY-3 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0007\n"
         "salt: inc-0001-ab12cd34\n```json\n{\"total_bytes\": 187}\n```")


class FakeApprover:
    def __init__(self) -> None:
        self.salts, self.calls = [], []

    def on_salt(self, incident, salt):
        self.salts.append((incident, salt))

    def on_approval(self, room, decision, d_id, approval, draft, user):
        self.calls.append((room, decision, d_id, draft["id"] if draft else None, user))
        return f"signed: {d_id}" if draft else "not signed: no draft"


@pytest.fixture()
def rooms():
    r = sw.Rooms()
    r.agents = {"payco-internal": {"payco-agent", "approver"}, "shopco-internal": {"shopco-agent"},
                sw.SHARED: {"notary", "mediator"}}
    return r


def msg(who, body, ts, addressed=False, mid=None):
    return {"sender_name": who, "body": body, "timestamp": ts, "addressed": addressed, "message_id": mid or f"m{ts}",
            "sender": f"@switch-x-{who}:s"}


def test_signs_only_an_addressed_approval_from_the_owner_for_the_agents_draft(rooms):
    ap = FakeApprover()
    sw.note_message(ap, rooms, "payco-internal", msg("payco-agent", BLOCK, 10, mid="draft"), live=True)
    got = sw.note_message(ap, rooms, "payco-internal", msg("priya", "@payco-agent @approver approve D-PAY-3", 20, True), live=True)
    assert ap.calls == [("payco-internal", "approve", "D-PAY-3", "draft", "priya")] and got[1] == "signed: D-PAY-3"


@pytest.mark.parametrize("who,addressed,room", [
    ("priya", False, "payco-internal"),     # not addressed to the approver: Switch didn't admit it (or no mention)
    ("user", True, "payco-internal"),       # addressed but not the owner (second line of defence)
    ("sam", True, "payco-internal"),        # the other company's owner
])
def test_everything_else_is_ignored(rooms, who, addressed, room):
    ap = FakeApprover()
    sw.note_message(ap, rooms, "payco-internal", msg("payco-agent", BLOCK, 10), live=True)
    assert sw.note_message(ap, rooms, room, msg(who, "@approver approve D-PAY-3", 20, addressed), live=True) is None
    assert ap.calls == []


def test_drafts_only_from_the_rooms_own_agent_and_never_approvals_from_history(rooms):
    ap = FakeApprover()
    sw.note_message(ap, rooms, "payco-internal", msg("user", BLOCK, 10, mid="fake"), live=True)        # forged draft
    sw.note_message(ap, rooms, "payco-internal", msg("priya", "@approver approve D-PAY-3", 20, True), live=False)
    assert ap.calls == []                                                                              # history
    sw.note_message(ap, rooms, "payco-internal", msg("priya", "@approver approve D-PAY-3", 30, True), live=True)
    assert ap.calls[-1][3] is None                                                                     # no real draft


def test_salts_only_from_the_notary_in_the_shared_room(rooms):
    ap = FakeApprover()
    sw.note_message(ap, rooms, sw.SHARED, msg("mediator", "Salt for INC-0002: `inc-0002-deadbeef`.", 1), live=True)
    sw.note_message(ap, rooms, sw.SHARED, msg("notary", "Salt for INC-0002: `inc-0002-ab12cd34`. Every fingerprint…", 2), live=True)
    assert ap.salts == [("INC-0002", "inc-0002-ab12cd34")]


def test_an_approval_is_decided_once(rooms):
    ap = FakeApprover()
    m = msg("priya", "@approver approve D-PAY-3", 20, True, mid="same")
    sw.note_message(ap, rooms, "payco-internal", m, live=True)
    sw.note_message(ap, rooms, "payco-internal", m, live=True)       # a replayed event
    assert len(ap.calls) == 1
