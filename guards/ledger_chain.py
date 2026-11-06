"""Hash-chained JSONL ledgers (stdlib only): append-only logs where changing or removing a line is detectable.

Every entry carries `prev` (the previous entry's `h`, or 64 zeros for the first) and `h`, the sha256 of the entry's
canonical JSON without `h`. Editing a line breaks its own hash; deleting or reordering lines breaks the next `prev`.
Truncating the tail is caught by comparing the head with an independent record (verify_ledger.py cross-checks each
allowed disclosure in the guard log against the approver's signed ledger, which lives in a Docker volume).

Used by disclosure_guard (.disclosures/guard.log.jsonl) and the approver (approvals.jsonl). Tests:
guards/tests/test_ledger_chain.py.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path

GENESIS = "0" * 64


def entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "h"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _last_hash(fh) -> str:
    fh.seek(0)
    last = GENESIS
    for raw in fh:
        try:
            last = json.loads(raw).get("h") or last
        except ValueError:
            continue
    return last


def append(path: Path, entry: dict, finalize=None) -> dict:
    """Append `entry` chained to the file's last entry, under an exclusive lock (hooks can run concurrently).
    `finalize(entry_with_prev)` may return a replacement entry (e.g. one with a signature) before it is hashed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            e = {**entry, "prev": _last_hash(fh)}
            if finalize:
                e = finalize(e)
            e["h"] = entry_hash(e)
            fh.seek(0, 2)
            fh.write(json.dumps(e) + "\n")
            fh.flush()
            return e
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def verify_lines(lines: list[str]) -> tuple[list[dict], list[str]]:
    """(entries, problems). No problems = an intact chain from the genesis entry."""
    entries, problems, prev = [], [], GENESIS
    for i, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            e = json.loads(raw)
        except ValueError:
            problems.append(f"line {i}: not JSON")
            continue
        if "h" not in e or "prev" not in e:
            problems.append(f"line {i}: not chained")
        elif e["prev"] != prev:
            problems.append(f"line {i}: prev does not match line {i - 1} (a line was removed, inserted or reordered)")
        elif entry_hash(e) != e["h"]:
            problems.append(f"line {i}: content changed after it was written")
        prev = e.get("h", prev)
        entries.append(e)
    return entries, problems


def verify(path: Path) -> tuple[list[dict], list[str]]:
    if not path.exists():
        return [], []
    return verify_lines(path.read_text(encoding="utf-8").splitlines())
