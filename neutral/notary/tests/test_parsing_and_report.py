from __future__ import annotations

import pytest
from conftest import SALT, disclosure, pay_disclosure, payco_fp, shop_disclosure, shopco_fp

from notary.disclosures import DisclosureError, find_in, parse
from notary.report import HELP, comparison
from notary.sse import SSEParser


def test_parse_valid_disclosures() -> None:
    d = parse(pay_disclosure(), "D-PAY-1", "m1")
    assert (d.side, d.approved_by, d.type, d.event, d.salt, d.message_id) == ("PAY", "priya", "delivery_fingerprint", "evt_0042", SALT, "m1")
    assert d.fingerprint and d.fingerprint["event_id"] == "evt_0042"
    s = parse(shop_disclosure(), "D-SHOP-1")
    assert s.side == "SHOP" and s.approved_by == "sam"


def test_ascii_separator_and_surrounding_text_accepted() -> None:
    body = "Here is the approved disclosure:\n" + pay_disclosure().replace("·", "-") + "\nthanks"
    assert parse(body, "D-PAY-1").salt == SALT
    assert find_in(body) == ["D-PAY-1"]


@pytest.mark.parametrize("body,needle", [
    ("type: delivery_fingerprint\nevent: evt_0042\nsalt: x", "no '[D-PAY-1"),
    ("[D-PAY-1 · approved by @priya]\ntype: delivery_fingerprint\nsalt: s1234", "missing event"),
    ("[D-PAY-1 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0042\nsalt: s1234\n", "no ```json"),
    ("[D-PAY-1 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0042\nsalt: s1234\n```json\n{oops\n```", "malformed"),
    ("[D-PAY-1 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0042\nsalt: s1234\n```json\n{\"a\": 1}\n```", "must have"),
])
def test_malformed_disclosures_explain_why(body: str, needle: str) -> None:
    with pytest.raises(DisclosureError, match=needle.replace("[", r"\[")):
        parse(body, "D-PAY-1")


def test_event_mismatch_between_header_and_fingerprint() -> None:
    with pytest.raises(DisclosureError, match="header says event evt_0007"):
        parse(disclosure("D-PAY-1", "priya", "delivery_fingerprint", payco_fp(), event_id="evt_0007"), "D-PAY-1")


def test_comparison_table_shows_name_plus_four() -> None:
    out = comparison(parse(pay_disclosure(), "D-PAY-1"), parse(shop_disclosure(), "D-SHOP-1"))
    assert "| path | PayCo bytes | ShopCo bytes | delta | match | escaped (PayCo/ShopCo) |" in out
    assert "| data.customer.name | 19 | 15 | +4 | no | yes/no |" in out
    assert "| data.customer.country | 4 | 4 | +0 | yes | no/no |" in out
    assert out.rstrip().endswith("First difference: data.customer.name, delta +4 bytes.")
    for speculation in ("because", "cause", "bug", "should", "fix", "probably"):
        assert speculation not in out.lower()


def test_identical_payloads() -> None:
    out = comparison(parse(pay_disclosure(fp=payco_fp(name="Jane Doe")), "D-PAY-1"),
                     parse(shop_disclosure(fp=shopco_fp(name="Jane Doe")), "D-SHOP-1"))
    assert "No difference" in out and "hashes match" in out


def test_salt_and_type_mismatch_rejected() -> None:
    pay = parse(pay_disclosure(), "D-PAY-1")
    other_salt = parse(shop_disclosure(salt="inc-0002-aaaa", fp=shopco_fp(salt="inc-0002-aaaa")), "D-SHOP-1")
    with pytest.raises(DisclosureError, match="different salts"):
        comparison(pay, other_salt)
    summary = parse(disclosure("D-SHOP-1", "sam", "failure_list", None), "D-SHOP-1")
    with pytest.raises(DisclosureError, match="not a verification_fingerprint"):
        comparison(pay, summary)


def test_help_lists_commands() -> None:
    assert "compare <D-PAY-n> <D-SHOP-n>" in HELP and "help" in HELP


def test_sse_parser_handles_chunking_comments_and_crlf() -> None:
    p = SSEParser()
    frames = p.feed(": keepalive\n\nid: 7\nevent: mes")
    assert frames == []
    frames = p.feed('sage\ndata: {"type":"message",\ndata: "sequence":7}\n\nevent: gap\r\ndata: {"reason":"x"}\r\n\r\n')
    assert [(f.event, f.id) for f in frames] == [("message", "7"), ("gap", None)]
    assert frames[0].data == {"type": "message", "sequence": 7}
    assert frames[1].data == {"reason": "x"}
