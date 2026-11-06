"""Fix 8: the approver signs and serves an approval only for the current incident and the salt the notary issued."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "guards"))          # disclosure_canon (copied next to the service in the image)
sys.path.insert(0, str(ROOT / "approver"))
pytest.importorskip("cryptography")
from approver import service  # noqa: E402


def draft(salt: str, d_id: str = "D-PAY-3") -> dict:
    return {"id": "p-draft", "message": f"DRAFT {d_id}\n[{d_id} · approved by @priya]\ntype: delivery_fingerprint\n"
                                        f"event: evt_0007\nsalt: {salt}\n```json\n{{\"total_bytes\": 187}}\n```"}


APPROVAL = {"id": "p-ok", "user_id": "u-priya", "create_at": 1_700_000_000_000}


@pytest.fixture()
def ap(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "DATA", tmp_path / "data")
    monkeypatch.setattr(service, "WS", tmp_path / "ws")
    return service.Approver()


def test_signs_and_serves_only_for_the_current_incident_and_issued_salt(ap):
    ap.on_salt("INC-0002", "inc-0002-ab12cd34")
    ap.on_approval("payco-internal", "approve", "D-PAY-3", APPROVAL, draft("inc-0002-ab12cd34"), "priya")
    assert ap.servable("D-PAY-3")["incident"] == "INC-0002"


def test_nothing_signed_before_the_notary_issues_a_salt(ap):
    ap.on_approval("payco-internal", "approve", "D-PAY-3", APPROVAL, draft("inc-0002-ab12cd34"), "priya")
    assert ap.servable("D-PAY-3") is None and "no incident salt" in ap.refusals[-1]["reason"]


@pytest.mark.parametrize("salt,why", [("inc-0002-deadbeef", "not issued"),     # made-up salt, right incident
                                      ("inc-0001-ab12cd34", "not the current")])  # previous incident's salt
def test_refuses_a_made_up_or_previous_incident_salt(ap, salt, why):
    ap.on_salt("INC-0001", "inc-0001-ab12cd34")
    ap.on_salt("INC-0002", "inc-0002-ab12cd34")
    ap.on_approval("payco-internal", "approve", "D-PAY-3", APPROVAL, draft(salt), "priya")
    assert ap.servable("D-PAY-3") is None and why in ap.refusals[-1]["reason"]


def test_an_approval_goes_stale_when_a_new_incident_starts_or_the_salt_rotates(ap):
    ap.on_salt("INC-0001", "inc-0001-ab12cd34")
    ap.on_approval("payco-internal", "approve", "D-PAY-3", APPROVAL, draft("inc-0001-ab12cd34"), "priya")
    assert ap.servable("D-PAY-3")
    ap.on_salt("INC-0001", "inc-0001-99999999")            # same id, new thread: the notary rotated the salt
    assert ap.servable("D-PAY-3") is None
    ap.on_salt("INC-0001", "inc-0001-ab12cd34")
    ap.on_salt("INC-0002", "inc-0002-00000000")            # a new incident
    assert ap.servable("D-PAY-3") is None


def test_salt_post_pattern_matches_the_notary_reply():
    m = service.SALT_POST_RE.search("Salt for INC-0004: `inc-0004-1a2b3c4d`. Every fingerprint in this incident must use it.")
    assert m and m.groups() == ("INC-0004", "inc-0004-1a2b3c4d")
