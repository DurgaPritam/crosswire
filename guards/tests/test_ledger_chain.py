"""Hash-chained ledgers: any edit, removal, insertion or reordering of a line is detected."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ledger_chain  # noqa: E402


def make(tmp_path: Path, n: int = 4) -> Path:
    f = tmp_path / "log.jsonl"
    for i in range(n):
        ledger_chain.append(f, {"i": i, "decision": "allow"})
    return f


def test_intact_chain_verifies(tmp_path):
    entries, problems = ledger_chain.verify(make(tmp_path))
    assert problems == [] and [e["i"] for e in entries] == [0, 1, 2, 3] and entries[0]["prev"] == ledger_chain.GENESIS


def test_edit_remove_insert_reorder_are_detected(tmp_path):
    lines = make(tmp_path).read_text().splitlines()
    edited = lines.copy()
    e = json.loads(edited[1]); e["decision"] = "block"; edited[1] = json.dumps(e)
    assert "content changed" in ledger_chain.verify_lines(edited)[1][0]
    assert "removed" in ledger_chain.verify_lines(lines[:1] + lines[2:])[1][0]
    assert ledger_chain.verify_lines([lines[0], lines[2], lines[1], lines[3]])[1]
    assert "not chained" in ledger_chain.verify_lines(lines + ['{"i": 9}'])[1][0]


def test_finalize_runs_before_hashing(tmp_path):
    f = tmp_path / "a.jsonl"
    e = ledger_chain.append(f, {"d_id": "D-PAY-1"}, lambda x: {**x, "sig": "s-" + x["prev"][:4]})
    assert e["sig"] == "s-0000" and ledger_chain.verify(f)[1] == []
