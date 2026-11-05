#!/usr/bin/env python3
"""Phase 5 live pass check for the Notary, in a throwaway room (so the demo rooms stay clean).

    python3 scripts/notary_selftest.py

1. Creates #notary-selftest (admin), with the notary and priya; admits priya's account to the notary there.
2. As priya: posts two hand-made disclosures for evt_0042 (wirecheck fingerprints) and `@notary compare`.
   PASS if the notary replies in-thread with data.customer.name at +4.
3. Restarts the notary container: PASS if it resumes, answers a new `@notary help`, and does not answer the
   compare a second time.
4. Archives the room and restores the notary's addressing policy (phase7 policies step).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "packages/wirecheck")]
import mmlib  # noqa: E402
import phase7  # noqa: E402
from wirecheck import fingerprint  # noqa: E402

ROOM = "notary-selftest"
SALT = "inc-0042-5e1f7c3a"
ROW = "| data.customer.name | 19 | 15 | +4 | no | yes/no |"


def event() -> dict:
    return {"id": "evt_0042", "type": "payment.succeeded", "created": 1762300800,
            "data": {"amount_cents": 4200, "currency": "EUR", "customer": {"id": "cus_0042", "name": "Chloé Martin", "country": "FR"}}}


def disclosure(d_id: str, owner: str, kind: str, ensure_ascii: bool) -> str:
    raw = json.dumps(event(), separators=(",", ":"), ensure_ascii=ensure_ascii).encode()
    fp = fingerprint(raw, SALT, "evt_0042")
    return (f"[{d_id} · approved by @{owner}]\ntype: {kind}\nevent: evt_0042\nsalt: {SALT}\n"
            "```json\n" + json.dumps(fp, indent=1) + "\n```")


def raw_yaml(gw: phase7.Gateway, text: str) -> dict:
    req = urllib.request.Request(gw.base + "/rooms/from-yaml", data=text.encode(), method="POST")
    req.add_header("Content-Type", "application/yaml")
    req.add_header("X-Requested-With", "XMLHttpRequest")
    with gw.opener.open(req, timeout=60) as resp:
        return json.loads(resp.read())


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", "compose", "--profile", "notary", *args], cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, "PATH": os.environ["PATH"] + f":{Path.home()}/.docker/bin"})


def main() -> int:
    e = mmlib.load_env()
    gw = phase7.admin(e)
    st = phase7.load_state()
    priya = mmlib.Mattermost(e["MM_URL"]).login("priya", e["MM_PRIYA_PASSWORD"])
    rooms = {r["name"]: r["id"] for r in phase7.items(gw.req("GET", "/rooms"), "rooms")}
    if ROOM not in rooms:
        raw_yaml(gw, f'room:\n  name: {ROOM}\n  description: "Notary live self-test (Phase 5)"\n'
                     f'  channel_type: channel_private\n  agents: [notary]\n  users: [priya, "{{$creator}}"]\n')
        rooms = {r["name"]: r["id"] for r in phase7.items(gw.req("GET", "/rooms"), "rooms")}
    room_id = rooms[ROOM]
    notary_id = st["notary_id"]
    shared, account = st["rooms"]["payco-shopco-shared"], st["platform_accounts"]["priya"]
    test_rules = [phase7._rule([shared], list(st["platform_accounts"].values()), [st.get("agents", {}).get("mediator")
                                                                                  or _agent_id(gw, "mediator")]),
                  phase7._rule([room_id], [account], [])]
    gw.req("PUT", f"/agents/{notary_id}/addressing-policy", {"policy": {"rules": test_rules}})
    time.sleep(3)
    ch = None
    for _ in range(20):
        ch = priya.channel(priya.team()["id"], ROOM)
        if ch:
            break
        time.sleep(2)
    if not ch:
        raise SystemExit(f"priya is not in #{ROOM}")
    results: list[tuple[str, bool]] = []
    try:
        for d_id, kind, ascii_ in (("D-PAY-1", "delivery_fingerprint", True), ("D-SHOP-1", "verification_fingerprint", False)):
            priya.send(ch["id"], disclosure(d_id, "priya" if ascii_ else "sam", kind, ascii_))
        cmd = priya.send(ch["id"], "@notary compare D-PAY-1 D-SHOP-1")
        posts = priya.wait([ch["id"]], cmd["create_at"], lambda ps: bool(mmlib.real(ps, "notary")), timeout=90, quiet=5,
                           exclude={cmd["id"]})
        replies = mmlib.real(posts, "notary")
        table = next((p for p in replies if ROW in p.message), None)
        results.append(("compare reply in thread shows data.customer.name +4", bool(table) and table.root_id == cmd["id"]))
        results.append(("ends with 'First difference: data.customer.name, delta +4 bytes.'",
                        bool(table) and table.message.rstrip().endswith("First difference: data.customer.name, delta +4 bytes.")))

        r = docker("restart", "notary")
        results.append(("notary container restarted", r.returncode == 0))
        time.sleep(12)
        logs = docker("logs", "--no-log-prefix", "--since", "30s", "notary").stdout
        results.append(("notary resumed (connected after restart)", "connected:" in logs))
        hello = priya.send(ch["id"], "@notary help")
        later = priya.wait([ch["id"]], cmd["create_at"], lambda ps: any("Commands" in p.message for p in mmlib.real(ps, "notary")),
                           timeout=60, quiet=10, exclude={cmd["id"], hello["id"]})
        tables = [p for p in mmlib.real(later, "notary") if ROW in p.message]
        results.append(("answers a new @notary help after restart", any("Commands" in p.message for p in mmlib.real(later, "notary"))))
        results.append(("no duplicate compare reply after restart", len(tables) == 1))
    finally:
        try:
            gw.req("POST", f"/rooms/{room_id}/archive")
        except phase7.GatewayError as exc:
            print(f"(could not archive #{ROOM}: {exc})")
        subprocess.run([sys.executable, str(ROOT / "scripts/phase7.py"), "policies"], cwd=ROOT, capture_output=True)
    for label, ok in results:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    return 0 if results and all(ok for _, ok in results) else 1


def _agent_id(gw: phase7.Gateway, name: str) -> str:
    return next(a["id"] for a in phase7.items(gw.req("GET", "/agents"), "agents") if a.get("name") == name)


if __name__ == "__main__":
    sys.exit(main())
