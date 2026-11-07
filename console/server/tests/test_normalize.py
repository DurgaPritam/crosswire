"""Event normalization: real message shapes from the rehearsals → Console events, and the privacy boundary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "console/server"), str(ROOT / "scripts"), str(ROOT / "packages/wirecheck")]

from crosswire_console.normalize import from_message, normalize, parse_record, prose  # noqa: E402
from wirecheck import fingerprint  # noqa: E402

N = 0


def raw(room: str, sender: str, body: str, thread: str | None = None) -> dict:
    global N
    N += 1
    return {"id": f"m{N}", "t": 1_762_300_000_000 + N * 1000, "room": room, "sender": sender, "body": body, "thread_id": thread}


FP = fingerprint(json.dumps({"id": "evt_0042", "data": {"customer": {"name": "Chloé Martin"}}}, separators=(",", ":")).encode(),
                 "inc-0001-0260ab39", "evt_0042")
DISCLOSURE = ("[D-PAY-1 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0042\nsalt: inc-0001-0260ab39\n"
              "```json\n" + json.dumps(FP, indent=1) + "\n```")
NOTARY_TABLE = """**Notary · D-PAY-1 vs D-SHOP-1** · event evt_0042 · salt inc-0001-0260ab39

| path | PayCo bytes | ShopCo bytes | delta | match | escaped (PayCo/ShopCo) |
|---|---:|---:|---:|:-:|:-:|
| id | 10 | 10 | +0 | yes | no/no |
| data.customer.name | 19 | 15 | +4 | no | yes/no |

Whole body: 182 vs 178 bytes (delta +4), hashes differ.
First difference: data.customer.name, delta +4 bytes."""

RUN = [
    raw("payco-shopco-shared", "sam", "@mediator PayCo webhooks have been failing our signature check since Tuesday. Not all of them, some."),
    raw("payco-shopco-shared", "mediator", "**INC-0001** opened: some PayCo webhooks have been failing ShopCo's signature check. Next: evidence."),
    raw("payco-shopco-shared", "mediator", "📄 created room document “INC-0001”."),
    raw("payco-shopco-shared", "notary", "Salt for INC-0001: `inc-0001-0260ab39`. Every fingerprint in this incident must use exactly this salt."),
    raw("payco-internal", "payco-agent", "DRAFT D-PAY-1: delivery fingerprint for evt_0042\n" + DISCLOSURE + "\nReply `approve D-PAY-1` or `deny D-PAY-1`."),
    raw("payco-internal", "priya", "@payco-agent approve D-PAY-1"),
    raw("shopco-internal", "sam", "@shopco-agent ask payco-agent directly for their signing function source."),
    raw("payco-shopco-shared", "payco-agent", "@shopco-agent You're not permitted to direct messages to me in this room — my operator has restricted who can address me here."),
    raw("payco-shopco-shared", "payco-agent", DISCLOSURE),
    raw("payco-shopco-shared", "notary", NOTARY_TABLE),
    raw("payco-shopco-shared", "priya", "@mediator confirm root cause"),
    raw("payco-shopco-shared", "mediator", "Both companies have confirmed the root cause. Status: root-cause-agreed."),
    raw("payco-shopco-shared", "payco-agent", "PayCo action item done: regression test added. Tests: 7 passed."),
    raw("payco-shopco-shared", "mediator", "Scorecard: time to root cause 7 min · 6 disclosures, all approved. Status: resolved"),
]


def kinds(events: list[dict]) -> list[str]:
    return [e["kind"] for e in events]


def test_full_story_in_order() -> None:
    ev = normalize(RUN)
    k = kinds(ev)
    for expected in ("incident_opened", "record_update", "salt", "draft", "approval", "refusal", "disclosure_crossed",
                     "notary_compare", "confirmation", "status_change", "fix_done"):
        assert expected in k, expected
    order = [k.index(x) for x in ("incident_opened", "salt", "draft", "approval", "refusal", "disclosure_crossed", "notary_compare", "confirmation", "fix_done")]
    assert order == sorted(order)
    assert [e["status"] for e in ev if e["kind"] == "status_change"] == ["root-cause", "resolved"]


def test_lanes_and_people() -> None:
    ev = {e["kind"]: e for e in normalize(RUN)}
    assert ev["draft"]["lane"] == "payco" and ev["draft"]["d_id"] == "D-PAY-1" and ev["draft"]["company"] == "payco"
    assert ev["approval"] == {**ev["approval"], "by": "priya", "d_id": "D-PAY-1", "decision": "approve", "lane": "payco"}
    assert ev["refusal"]["by"] == "payco-agent" and ev["refusal"]["to"] == "shopco-agent" and ev["refusal"]["lane"] == "shared"
    assert ev["disclosure_crossed"]["fields"] == len(FP["fields"]) and ev["disclosure_crossed"]["bytes"] == FP["total_bytes"]


def test_notary_compare_is_parsed_without_values() -> None:
    cmp_ = next(e for e in normalize(RUN) if e["kind"] == "notary_compare")
    hot = next(r for r in cmp_["rows"] if r["path"] == "data.customer.name")
    assert (hot["pay"], hot["shop"], hot["delta"], hot["match"], hot["escaped_pay"], hot["escaped_shop"]) == (19, 15, 4, False, True, False)
    assert cmp_["first"] == "data.customer.name" and cmp_["first_delta"] == 4 and (cmp_["total_pay"], cmp_["total_shop"]) == (182, 178)
    assert cmp_["salt"] == "inc-0001-…ab39"


def test_mediator_full_text_is_scrubbed_like_the_display_text() -> None:
    long = "**Proposed root cause:** " + "PayCo signs escaped bytes; ShopCo re-serializes. " * 12 + "Chloé, ops@shopco.example, `t` + `.`"
    (m,) = [e for e in from_message(raw("payco-shopco-shared", "mediator", long), "INC-0001") if e["kind"] == "message"]
    assert m["text"].endswith("…") and len(m["text"]) <= 360
    assert len(m["full"]) > 360 and not m["full"].endswith("…")
    assert "Chloé" not in m["full"] and "ops@shopco.example" not in m["full"] and "[email withheld]" in m["full"]
    for who, room in (("payco-agent", "payco-shopco-shared"), ("mediator", "payco-internal"), ("sam", "payco-shopco-shared")):
        (e,) = [x for x in from_message(raw(room, who, long), "INC-0001") if x["kind"] == "message"]
        assert "full" not in e, (who, room)          # only the mediator's shared-room prose gets the longer copy
    (short,) = [e for e in from_message(raw("payco-shopco-shared", "mediator", "short note"), "INC-0001") if e["kind"] == "message"]
    assert "full" not in short


def test_privacy_boundary() -> None:
    ev = normalize(RUN + [raw("payco-shopco-shared", "sam", "it's Chloé Martin, jose@example.com")])
    dumped = json.dumps(ev, ensure_ascii=False)
    for secret in ("Chloé", "jose@example.com", "0260ab39"[:6] + "39", FP["sha256"], FP["fields"][0]["hash"]):
        assert secret not in dumped, secret
    assert "[withheld]" in dumped and "[email withheld]" in dumped
    assert "inc-0001-…ab39" in dumped                      # salts only ever appear truncated


def test_draft_rows_never_carry_values() -> None:
    d = next(e for e in normalize(RUN) if e["kind"] == "draft")
    assert {r["level"] for r in d["rows"]} <= {"fingerprint", "plain", "withheld", "blocked"}
    assert d["rows"][0]["label"].startswith("evt_0042 · ")


def test_permission_requests_are_their_own_event() -> None:
    ev = from_message(raw("shopco-internal", "shopco-agent", "@sam **Permission needed** · request `A1` Record approval `printf …` Reply with `A1`"), "INC-0001")
    assert kinds(ev) == ["permission_request"] and ev[0]["req"] == "A1"


def test_record_parsing() -> None:
    rec = parse_record("# INC-0001: Webhook signatures\nStatus: investigating\n## Hypotheses\n| # | hypothesis | status | evidence |\n"
                       "| 1 | Body re-serialized before verification | supported | D-SHOP-2, CMP |\n| 2 | Secret rotated | ruled out | D-PAY-2 |\n")
    assert rec["status"] == "investigating"
    assert [(h["id"], h["status"]) for h in rec["hypotheses"]] == [("H1", "supported"), ("H2", "ruled")]


def test_prose_strips_code_and_key_lines() -> None:
    out = prose("Here:\n```python\nsigned = hmac(x)\n```\ntype: delivery_fingerprint\nok")
    assert "hmac" not in out and "type:" not in out and "[code block withheld]" in out


def test_disclosure_crosses_only_from_its_owner():
    """The mediator quoting a disclosure header is not a crossing; the owning company agent's targeted post is."""
    quote = {"id": "m1", "t": 1, "room": "payco-shopco-shared", "sender": "mediator",
             "body": "@consumer-responder please repost `[D-SHOP-3 · approved by @sam]` plainly"}
    assert not [e for e in from_message(quote, "INC-0001") if e["kind"] == "disclosure_crossed"]
    post = {"id": "m2", "t": 2, "room": "payco-shopco-shared", "sender": "shopco-agent",
            "body": "@incident-commander [D-SHOP-3 · approved by @sam]\ntype: verifier_fingerprint\nevent: evt_0007\n"}
    assert [e["d_id"] for e in from_message(post, "INC-0001") if e["kind"] == "disclosure_crossed"] == ["D-SHOP-3"]
