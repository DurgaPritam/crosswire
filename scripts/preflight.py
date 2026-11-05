#!/usr/bin/env python3
"""Preflight for a full rehearsal (~2 minutes). A run starts only when every check passes.

    python3 scripts/preflight.py            # clean, check, write rehearsals/preflight-<ts>.json, exit 0/1

1. Clean Switch state: no INC-*/PREFLIGHT record left in the shared room (deleted as admin if found).
2. Roles: incident-commander, provider-responder, consumer-responder and notary all held (!roles).
3. Notary connected: `@notary help` answers.
4. Each agent does its critical actions with its normal tools, and NOTHING asks for permission:
   - payco-agent / shopco-agent (asked by Priya / Sam in their private room): write an approval file, call an
     evidence tool, post a DRAFT in the private room, hop to the shared room and post, try the DRAFT there (the
     guard must block it: rule g), hop back, run ./bin/test (the fix phase's test command).
   - mediator (asked by Priya in the shared room): `@notary salt INC-9999`, create, update and delete a room
     document named PREFLIGHT.
   Any "Permission needed" post fails the preflight (fix the settings or give the agent an allowed tool).
5. The Console's observer is receiving events (skipped until the Console server is running).
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mmlib  # noqa: E402
import phase7  # noqa: E402
import toolpath  # noqa: E402

SHARED, PAY_IN, SHOP_IN = "payco-shopco-shared", "payco-internal", "shopco-internal"
ROLES = ("incident-commander", "provider-responder", "consumer-responder", "notary")
ROLE_HOLDER = {"incident-commander": "mediator", "provider-responder": "payco-agent", "consumer-responder": "shopco-agent"}
CONSOLE_HEALTH = "http://127.0.0.1:7300/api/health"
WAIT = 240

COMPANY_TASK = """PREFLIGHT (a setup check, not an incident). Use your normal tools, no workarounds:
1) With your Write tool create .disclosures/approvals/{p}-0.json containing {{"id": "{p}-0", "status": "preflight"}}.
2) Call your evidence tool {tool} and note only the number of results.
3) Post exactly `DRAFT {p}-0: preflight check` in this room.
4) connect_to_room to #payco-shopco-shared, post exactly `PREFLIGHT hop ok from {agent}`, then try to post
   `DRAFT {p}-0: preflight check` there too (your guard should block that: expected), then connect_to_room back here.
5) Run exactly `./bin/test` with Bash (your one test command) and note only the number of tests passed.
6) Reply here with one line per step: ok or failed (quote any error)."""
MEDIATOR_TASK = """@mediator PREFLIGHT (a setup check, not an incident). Use your normal tools:
1) Post `@notary salt INC-9999` here. 2) Create a room document named PREFLIGHT with content `ok`.
3) Update it to `ok 2`. 4) Delete it. 5) Reply with one line per step: ok or failed (quote any error)."""


class Check:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def __call__(self, label: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((label, ok, detail))
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' (' + detail + ')') if detail else ''}", flush=True)
        return ok

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.rows)


def clean_state(gw: phase7.Gateway, shared_id: str) -> int:
    """The ONLY admin write in the run cycle: delete the previous incident's record (a room document named INC-nnnn
    in the shared room). Nothing else is created, edited or deleted. Every call is in .tmp/admin-api.log.jsonl."""
    docs = phase7.items(gw.req("GET", f"/rooms/{shared_id}/documents"), "documents")
    stale = [d for d in docs if re.fullmatch(r"INC-\d{4}", d.get("name", ""))]
    for d in stale:
        print(f"  cleanup (admin): DELETE /gateway/documents/{d['id']} (record {d['name']})", flush=True)
        gw.req("DELETE", f"/documents/{d['id']}")
    return len(stale)


def roles_held(mm: mmlib.Mattermost, ch: str) -> dict[str, str]:
    sent = mm.send(ch, "!roles")
    posts = mm.wait([ch], sent["create_at"], lambda ps: any("Roles in this room" in p.message for p in ps), timeout=60, quiet=2,
                    exclude={sent["id"]})
    text = next((p.message for p in posts if "Roles in this room" in p.message), "")
    held = {}
    for role in ROLES:
        m = re.search(rf"\*\*{re.escape(role)}\*\*.*?(held by ([\w .-]+?)(?:\s+-|\s*$|\n))", text, re.S)
        if m and "free" not in text.split(f"**{role}**", 1)[1].split("\n", 1)[0].split("- **", 1)[0]:
            held[role] = m.group(2).strip()
    return held


def main() -> int:
    started = datetime.now()
    e = mmlib.load_env()
    gw = phase7.admin(e)
    st = phase7.load_state()
    priya = mmlib.Mattermost(e["MM_URL"]).login("priya", e["MM_PRIYA_PASSWORD"])
    sam = mmlib.Mattermost(e["MM_URL"]).login("sam", e["MM_SAM_PASSWORD"])
    chans = {SHARED: priya.channel(priya.team()["id"], SHARED)["id"], PAY_IN: priya.channel(priya.team()["id"], PAY_IN)["id"],
             SHOP_IN: sam.channel(sam.team()["id"], SHOP_IN)["id"]}
    check = Check()
    print("preflight:", flush=True)

    tools = toolpath.resolve()
    missing = [n for n in toolpath.REQUIRED if not tools[n]]
    check("tools resolve without a login shell (docker, just, git, node, npm)", not missing,
          "missing: " + ", ".join(missing) if missing else "uv " + ("found" if tools["uv"] else "not installed (optional)"))

    import socket
    down = []
    for name, port in (("payco-api", 7001), ("shopco-app", 7002), ("payco-evidence", 7101), ("shopco-evidence", 7102)):
        with socket.socket() as s:
            s.settimeout(2)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                down.append(f"{name}:{port}")
    if not check("services up (payco-api, shopco-app, both evidence servers)", not down, ", ".join(down)):
        print("preflight FAILED early: start the services (just up)", flush=True)
        return 1

    drift = phase7.instructions_drift(gw)
    check("agents' Switch instructions match their AGENT.md", not drift,
          (", ".join(drift) + ": sync BETWEEN runs with `.venv/bin/python scripts/phase7.py instructions`, then restart "
           "the agent sessions; rehearse.py no longer patches agent definitions itself") if drift else "")

    removed = clean_state(gw, st["rooms"][SHARED])
    left = [d["name"] for d in phase7.items(gw.req("GET", f"/rooms/{st['rooms'][SHARED]}/documents"), "documents")
            if re.match(r"^(INC-|PREFLIGHT)", d.get("name", ""))]
    check("no open incident record in the shared room", not left,
          (f"still there: {', '.join(left)} (a PREFLIGHT leftover is never deleted by this script: delete it in Switch Console)"
           if left else f"removed {removed} stale incident record(s)" if removed else ""))

    held = roles_held(priya, chans[SHARED])
    for role, agent in ROLE_HOLDER.items():
        if role not in held:   # a restarted session dropped it: ask the agent to take it back
            asker = sam if agent == "shopco-agent" else priya
            asker.send(chans[SHARED], f"@{agent} PREFLIGHT: please take the {role} role again, then reply ok.")
    if len(held) < len(ROLES):
        time.sleep(45)
        held = roles_held(priya, chans[SHARED])
    check("all four roles held", all(r in held for r in ROLES), ", ".join(f"{r}: {held.get(r, 'FREE')}" for r in ROLES))

    sent = priya.send(chans[SHARED], "@notary help")
    posts = priya.wait([chans[SHARED]], sent["create_at"], lambda ps: bool(mmlib.real(ps, "notary")), timeout=60, quiet=2,
                       exclude={sent["id"]})
    check("notary connected (answers help)", any("Commands" in p.message for p in mmlib.real(posts, "notary")))

    t0 = int(time.time() * 1000)
    ours = set()
    for human, room, agent, p, tool in ((priya, PAY_IN, "payco-agent", "D-PAY", "list_failed_deliveries"),
                                        (sam, SHOP_IN, "shopco-agent", "D-SHOP", "list_signature_failures")):
        ours.add(human.send(chans[room], f"@{agent} " + COMPANY_TASK.format(p=p, tool=tool, agent=agent))["id"])
    ours.add(priya.send(chans[SHARED], MEDIATOR_TASK)["id"])

    def finished(ps: list[mmlib.Post]) -> bool:
        replies = {a: [x for x in mmlib.real(ps, a) if re.search(r"\b(ok|failed)\b", x.message, re.I) and re.search(r"[1-5]\)|step", x.message, re.I)]
                   for a in ("payco-agent", "shopco-agent", "mediator")}
        return all(replies.values())
    posts = priya.wait([chans[SHARED], chans[PAY_IN]], t0, lambda ps: False, timeout=5, quiet=0, exclude=ours)  # warm up
    deadline = time.monotonic() + WAIT
    seen: dict[str, tuple[str, mmlib.Post]] = {}
    while time.monotonic() < deadline:
        for name, cid in chans.items():
            client = sam if name == SHOP_IN else priya
            for p in client.posts_since(cid, t0 - 1):
                if p.id not in ours and p.create_at >= t0:  # `since` also returns OLD posts edited later
                    seen[p.id] = (name, p)
        if finished([p for _, p in seen.values()]):
            time.sleep(10)
            break
        time.sleep(5)
    posts_by_room = {n: [p for (rn, p) in seen.values() if rn == n] for n in chans}
    allp = [p for _, p in seen.values()]

    # every agent post must come from that agent's own bot. In run 4 the bridge posted some agent messages through the
    # operator's account ("admin"), which the driver and the grader can't attribute: catch it before a run starts
    impostor = [f"#{n} {_short(p.message)}" for n, ps in posts_by_room.items() for p in mmlib.real(ps)
                if not p.from_bot and p.username not in ("priya", "sam")]
    check("every agent post came from its own bot (none posted as a person)", not impostor, "; ".join(impostor[:3]))
    perms = [f"{p.label} in #{n}" for n, ps in posts_by_room.items() for p in ps if "permission needed" in p.message.lower()]
    check("no permission request from any agent", not perms, "; ".join(perms))
    for agent, room, p in (("payco-agent", PAY_IN, "D-PAY"), ("shopco-agent", SHOP_IN, "D-SHOP")):
        ws = ROOT / "workspace" / agent.split("-")[0]
        check(f"{agent} wrote its approval file", (ws / ".disclosures" / "approvals" / f"{p}-0.json").exists())
        check(f"{agent} posted a draft in its private room",
              any(m.is_by(agent) and f"DRAFT {p}-0" in m.message for m in posts_by_room[room]))
        check(f"{agent} hopped to the shared room and posted",
              any(m.is_by(agent) and f"PREFLIGHT hop ok from {agent}" in m.message for m in posts_by_room[SHARED]))
        check(f"{agent}'s guard blocked the draft in the shared room",
              not any(m.is_by(agent) and f"DRAFT {p}-0" in m.message for m in posts_by_room[SHARED])
              and _guard_blocked_room(ws))
        report = " ".join(m.message for m in mmlib.real(posts_by_room[room], agent))
        step2 = re.search(r"\b2\)\s*(ok|failed)\b[^\n]*", report, re.I)   # the agent's own verdict for step 2
        step5 = re.search(r"\b5\)\s*(ok|failed)\b[^\n]*", report, re.I)
        check(f"{agent} ran ./bin/test without a prompt", bool(step5) and step5.group(1).lower() == "ok",
              _short(step5.group(0) if step5 else report))
        check(f"{agent} called its evidence tool", bool(step2) and step2.group(1).lower() == "ok" and bool(re.search(r"\b6\b", step2.group(0))),
              _short(step2.group(0) if step2 else report))
    med = " ".join(m.message for m in mmlib.real(posts_by_room[SHARED], "mediator"))
    check("mediator got a salt from the notary", any(re.search(r"inc-9999-[0-9a-f]{8}", m.message) for m in mmlib.real(posts_by_room[SHARED], "notary")))
    check("mediator created, updated and deleted a room document",
          all(w in " ".join(m.message for m in allp) for w in ("created room document", "updated room document"))
          and not [d for d in phase7.items(gw.req("GET", f"/rooms/{st['rooms'][SHARED]}/documents"), "documents") if d.get("name") == "PREFLIGHT"],
          _short(med))

    try:
        with urllib.request.urlopen(CONSOLE_HEALTH, timeout=3) as r:
            health = json.loads(r.read())
        check("console observer receiving events", health.get("events_received", 0) > 0 and health.get("observer") == "connected",
              f"{health.get('events_received')} events")
    except OSError:
        print("  SKIP  console observer (console server not running yet)", flush=True)

    clean_state(gw, st["rooms"][SHARED])
    out = ROOT / "rehearsals" / f"preflight-{started:%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"started": started.isoformat(timespec="seconds"), "passed": check.passed,
                               "checks": [{"check": l, "ok": ok, "detail": d} for l, ok, d in check.rows]}, indent=1))
    print(f"preflight {'PASSED' if check.passed else 'FAILED'} -> {out.relative_to(ROOT)}", flush=True)
    return 0 if check.passed else 1


def _guard_blocked_room(ws: Path) -> bool:
    log = ws / ".disclosures" / "guard.log.jsonl"
    return log.exists() and any("room" in json.loads(l).get("rules", []) for l in log.read_text().splitlines() if l.strip())


def _short(text: str) -> str:
    return " ".join(text.split())[:160]


if __name__ == "__main__":
    sys.exit(main())
