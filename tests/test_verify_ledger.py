"""verify_ledger: the approver's ledger must be chained and signed; every allowed disclosure must match a signature."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "guards"))
import ledger_chain  # noqa: E402
import verify_ledger  # noqa: E402

ed = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
ser = pytest.importorskip("cryptography.hazmat.primitives.serialization")


def signed_ledger(tmp_path: Path, key, records: list[dict]) -> list[str]:
    f = tmp_path / "approvals.jsonl"
    for r in records:
        ledger_chain.append(f, r, lambda e: {**e, "sig": key.sign(json.dumps(e, sort_keys=True, separators=(",", ":")).encode()).hex()})
    return f.read_text().splitlines()


def pub(key) -> bytes:
    return key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)


REC = {"d_id": "D-PAY-1", "status": "approved", "sha256": "ab" * 32, "incident": "INC-0002"}


def test_signed_chain_verifies_and_forged_entry_does_not(tmp_path):
    k = ed.Ed25519PrivateKey.generate()
    lines = signed_ledger(tmp_path, k, [REC, {**REC, "d_id": "D-PAY-2"}])
    entries, problems = verify_ledger.verify_approver(lines, pub(k))
    assert problems == [] and len(entries) == 2
    forged = signed_ledger(tmp_path / "x", ed.Ed25519PrivateKey.generate(), [REC])   # someone else's key
    assert any("signature invalid" in p for p in verify_ledger.verify_approver(forged, pub(k))[1])


def test_cross_check_flags_an_allowed_disclosure_without_a_matching_signature():
    allowed = {"payco": [{"decision": "allow", "ts": "t", "disclosures": [{"d_id": "D-PAY-1", "sha256": "ab" * 32, "incident": "INC-0002"}]}]}
    assert verify_ledger.cross_check(allowed, [REC]) == []
    assert verify_ledger.cross_check(allowed, [{**REC, "sha256": "cd" * 32}])          # different evidence
    assert verify_ledger.cross_check(allowed, [{**REC, "incident": "INC-0001"}])       # other incident
    assert verify_ledger.cross_check(allowed, [])                                     # approval removed
