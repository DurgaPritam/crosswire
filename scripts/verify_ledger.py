#!/usr/bin/env python3
"""`just verify-ledger`: prove the disclosure records were not changed, removed or invented after the fact.

1. Each company's guard log (.disclosures/guard.log.jsonl) is an intact hash chain.
2. The approver's ledger (GET /ledger) is an intact hash chain and every entry carries a valid Ed25519 signature
   from the approver's key (the chain link is inside the signature, so a removed approval can't be hidden).
3. Every disclosure the guard ALLOWED names a D-id and evidence digest that the approver signed as approved, for the
   same incident. A guard log that lost its tail can't hide an approval either: the approver's ledger outlives it.

Read-only. Exit 0 = all intact; 1 = a problem (each one is printed).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "guards"))
import ed25519_verify  # noqa: E402
import ledger_chain  # noqa: E402

WS = ROOT / "workspace"
APPROVER = os.environ.get("APPROVER_URL", "http://127.0.0.1:7400")


def fetch(path: str) -> dict:
    with urllib.request.urlopen(APPROVER + path, timeout=5) as r:
        return json.loads(r.read())


def verify_approver(lines: list[str], pub: bytes) -> tuple[list[dict], list[str]]:
    entries, problems = ledger_chain.verify_lines(lines)
    for i, e in enumerate(entries, 1):
        body = {k: v for k, v in e.items() if k not in ("h", "sig")}
        payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        if not ed25519_verify.verify(pub, payload, bytes.fromhex(e.get("sig") or "00")):
            problems.append(f"approver entry {i} ({e.get('d_id')}): signature invalid")
    return entries, problems


def cross_check(guard: dict[str, list[dict]], approvals: list[dict]) -> list[str]:
    signed = {(a["d_id"], a.get("sha256"), a.get("incident")) for a in approvals if a.get("status") == "approved"}
    problems = []
    for company, entries in guard.items():
        for e in entries:
            for d in e.get("disclosures", []) if e.get("decision") == "allow" else []:
                if (d.get("d_id"), d.get("sha256"), d.get("incident")) not in signed:
                    problems.append(f"{company}: allowed {d.get('d_id')} at {e.get('ts')} has no matching signed approval")
    return problems


def main() -> int:
    problems: list[str] = []
    guard: dict[str, list[dict]] = {}
    for company in ("payco", "shopco"):
        entries, bad = ledger_chain.verify(WS / company / ".disclosures" / "guard.log.jsonl")
        guard[company] = entries
        problems += [f"{company} guard log: {b}" for b in bad]
        n = sum(len(e.get("disclosures", [])) for e in entries if e.get("decision") == "allow")
        print(f"  {company} guard log: {len(entries)} entries, chain {'intact' if not bad else 'BROKEN'}; {n} signed disclosure(s) allowed")
    try:
        pub = bytes.fromhex(fetch("/pubkey")["ed25519"])
        approvals, bad = verify_approver(fetch("/ledger")["lines"], pub)
    except OSError as exc:
        print(f"  approver: unreachable at {APPROVER} ({exc})")
        return 1
    problems += [f"approver ledger: {b}" for b in bad]
    print(f"  approver ledger: {len(approvals)} signed decision(s), chain {'intact' if not bad else 'BROKEN'}")
    problems += cross_check(guard, approvals)
    for p in problems:
        print(f"  FAIL {p}")
    print("ledgers verified" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
