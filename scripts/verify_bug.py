#!/usr/bin/env python3
"""Check the last simulation run against both companies' private databases.

    scripts/verify_bug.py [--expect bug|fixed] [--project crosswire] [--sim .tmp/last-simulate.json]

--expect bug   (just verify-bug):   exactly the 6 non-ASCII events fail, all 54 ASCII pass,
                                    on BOTH sides (PayCo saw 401, ShopCo marked them failed).
--expect fixed (just verify-fixed): all 60 pass.

This is test-harness code: it reads PayCo's and ShopCo's private volumes (via
`docker compose cp`), which no agent and no evidence server ever does across companies.
It prints event ids only, never customer names.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def copy_db(project: str, service: str, path: str, dest: Path) -> Path:
    out = dest / Path(path).name
    env = {**os.environ, "PATH": os.environ.get("PATH", "") + f":{Path.home()}/.docker/bin"}
    subprocess.run(["docker", "compose", "-p", project, "cp", f"{service}:{path}", str(out)],
                   cwd=ROOT, check=True, capture_output=True, env=env)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", choices=["bug", "fixed"], default="bug")
    ap.add_argument("--project", default="crosswire")
    ap.add_argument("--sim", default=str(ROOT / ".tmp" / "last-simulate.json"))
    args = ap.parse_args()

    sim_path = Path(args.sim)
    if not sim_path.exists():
        print(f"error: {sim_path} not found; run `just simulate` first", file=sys.stderr)
        return 2
    events = json.loads(sim_path.read_text())["events"]
    ids = [e["event_id"] for e in events]

    with tempfile.TemporaryDirectory() as tmp:
        try:
            payco = sqlite3.connect(copy_db(args.project, "payco-api", "/data/payco/deliveries.db", Path(tmp)))
            shopco = sqlite3.connect(copy_db(args.project, "shopco-worker", "/data/shopco/jobs.db", Path(tmp)))
        except subprocess.CalledProcessError as exc:
            print(f"error: could not copy a private db ({exc.stderr.decode().strip()}). Is `just up` running?", file=sys.stderr)
            return 2
        sent: dict[str, tuple[bool, int | None]] = {}
        for event_id, body, status in payco.execute(
                "SELECT event_id, body, response_status FROM deliveries ORDER BY seq"):
            name = json.loads(body)["data"]["customer"]["name"]
            sent[event_id] = (not name.isascii(), status)
        jobs = {event_id: status for event_id, status in shopco.execute(
            "SELECT event_id, status FROM jobs ORDER BY id")}

    missing = [i for i in ids if i not in sent or i not in jobs]
    if missing:
        print(f"FAIL: {len(missing)} event(s) missing from a delivery log or job queue: {missing[:5]}…")
        return 1
    non_ascii = {i for i in ids if sent[i][0]}
    payco_failed = {i for i in ids if sent[i][1] != 202}
    shopco_failed = {i for i in ids if jobs[i] != "verified"}
    passed = len(ids) - len(shopco_failed)

    print(f"events: {len(ids)} ({ids[0]}..{ids[-1]}) · non-ASCII names: {len(non_ascii)} {sorted(non_ascii)}")
    print(f"PayCo  saw non-202 for: {sorted(payco_failed)}")
    print(f"ShopCo signature mismatches: {sorted(shopco_failed)}")
    print(f"result: {passed}/{len(ids)} verified")

    if args.expect == "bug":
        ok = (len(ids) == 60 and len(non_ascii) == 6 and shopco_failed == non_ascii
              and payco_failed == non_ascii)
        verdict = "exactly the 6 non-ASCII events fail; all 54 ASCII events pass" if ok else \
            "expected exactly the 6 non-ASCII events to fail on both sides"
    else:
        ok = not shopco_failed and not payco_failed and len(ids) == 60
        verdict = "60/60 pass" if ok else "expected 60/60 to pass"
    print(("PASS: " if ok else "FAIL: ") + verdict)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
