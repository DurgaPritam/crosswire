#!/usr/bin/env python3
"""Phase 7 automation: wire Crosswire into the local Switch server through its Gateway API.

    python3 scripts/phase7.py plan                 # what would happen (no admin login needed)
    python3 scripts/phase7.py all                  # every step below, in order (idempotent)
    python3 scripts/phase7.py <step> [<step> ...]  # users notary template rooms claims policies roles smoke

Needs SWITCH_ADMIN_EMAIL / SWITCH_ADMIN_PASSWORD (and the MM_* logins) in the gitignored .env.
Ownership model (UPDATE-003): the admin owns all four agents; addressing rules name Priya and Sam.
Writes ids only to switch/state/ (gitignored) and policy read-backs to switch/policies/. Never prints a
password, a session cookie, an API key or a link code.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_templates  # noqa: E402
import mmlib  # noqa: E402

STATE_DIR = ROOT / "switch" / "state"
STATE = STATE_DIR / "phase7.json"
POLICIES = ROOT / "switch" / "policies"
ROOM_NAMES = {"payco-internal": "payco-internal", "shopco-internal": "shopco-internal",
              "payco-shopco-shared": "payco-shopco-shared"}
PEOPLE = {"priya": "Priya (PayCo)", "sam": "Sam (ShopCo)"}
AGENT_NAMES = ["payco-agent", "shopco-agent", "mediator", "notary"]
STEPS = ["users", "notary", "template", "rooms", "claims", "policies", "roles", "smoke"]


def say(msg: str) -> None:
    print(f"[phase7] {msg}", flush=True)


class GatewayError(RuntimeError):
    pass


class Gateway:
    """Cookie-authenticated client for /gateway on the agent bridge."""

    def __init__(self, bridge: str) -> None:
        self.base = bridge.rstrip("/") + "/gateway"
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.who = "?"

    def req(self, method: str, path: str, body: Any = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, method=method)
        r.add_header("Content-Type", "application/json")
        r.add_header("Accept", "application/json")
        r.add_header("X-Requested-With", "XMLHttpRequest")
        try:
            with self.opener.open(r, timeout=60) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read())
            except Exception:
                detail = {}
            raise GatewayError(f"{method} /gateway{path.split('?')[0]} as {self.who} → HTTP {exc.code}: "
                               f"{json.dumps(detail)[:600]}") from None

    def login(self, email: str, password: str) -> "Gateway":
        self.who = email
        self.req("POST", "/auth/login", {"email": email, "password": password})
        return self


# ------------------------------------------------------------------ state / env


def load_state() -> dict[str, Any]:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, sort_keys=True))


def env() -> dict[str, str]:
    return mmlib.load_env()


def admin(e: dict[str, str]) -> Gateway:
    missing = [k for k in ("SWITCH_ADMIN_EMAIL", "SWITCH_ADMIN_PASSWORD", "SWITCH_BRIDGE_URL") if not e.get(k)]
    if missing:
        raise SystemExit(f"missing in .env: {missing}. Add the local Switch admin login (never commit .env).")
    return Gateway(e["SWITCH_BRIDGE_URL"]).login(e["SWITCH_ADMIN_EMAIL"], e["SWITCH_ADMIN_PASSWORD"])


def items(payload: Any, *keys: str) -> list[dict[str, Any]]:
    """Lists come back bare or wrapped ({users: [...]}, {items: [...]}, ...)."""
    if isinstance(payload, list):
        return payload
    for k in (*keys, "items", "results", "data"):
        if isinstance(payload, dict) and isinstance(payload.get(k), list):
            return payload[k]
    raise GatewayError(f"unexpected list shape: keys {sorted(payload) if isinstance(payload, dict) else type(payload)}")


def person_email(name: str) -> str:
    return f"{name}@example.com"


# ------------------------------------------------------------------ steps


def step_users(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    users = items(gw.req("GET", "/users"), "users")
    for name, display in PEOPLE.items():
        found = next((u for u in users if u.get("email") == person_email(name)), None)
        if found:
            st.setdefault("users", {})[name] = found["id"]
            say(f"user {name}: exists ({found['id']})")
            if not e.get(f"SWITCH_{name.upper()}_PASSWORD"):
                say(f"  WARNING: no SWITCH_{name.upper()}_PASSWORD in .env; claims for {name} will fail")
            continue
        pw = secrets.token_urlsafe(18) + "Aa1!"
        created = gw.req("POST", "/users", {"name": display, "email": person_email(name), "password": pw, "role": "user"})
        mmlib.set_env_value(f"SWITCH_{name.upper()}_PASSWORD", pw)
        st.setdefault("users", {})[name] = created["id"]
        say(f"user {name}: created ({created['id']}), password saved to .env")
    me = gw.req("GET", "/auth/me")
    st["admin_user_id"] = me.get("id")


def step_notary(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    creds = ROOT / "neutral/notary/.credentials.json"
    if not creds.exists():
        key = gw.req("POST", "/api-keys", {"label": "crosswire notary registration"})
        token = key.get("key")
        if not token:
            raise GatewayError(f"api-keys returned no key (fields: {sorted(key)})")
        r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "notary.register"], cwd=ROOT / "neutral/notary",
                           env={**os.environ, "NOTARY_REGISTRATION_TOKEN": token, "SWITCH_BRIDGE_URL": e["SWITCH_BRIDGE_URL"]},
                           capture_output=True, text=True)
        say("notary register: " + (r.stdout.strip() or r.stderr.strip())[-300:])
        if r.returncode != 0:
            raise GatewayError("notary registration failed")
    st["notary_id"] = json.loads(creds.read_text())["id"]
    r = subprocess.run(["docker", "compose", "--profile", "notary", "up", "-d", "--build", "notary"], cwd=ROOT,
                       capture_output=True, text=True, env={**os.environ, "PATH": os.environ["PATH"] + f":{Path.home()}/.docker/bin"})
    say("notary container: " + ("running" if r.returncode == 0 else f"FAILED {r.stderr[-300:]}"))


def _controller(gw: Gateway) -> dict[str, Any]:
    for path in ("/management/controllers", "/controllers"):
        try:
            ctrls = items(gw.req("GET", path), "controllers")
        except GatewayError as exc:
            if "HTTP 404" in str(exc):
                continue
            raise
        online = [c for c in ctrls if c.get("online") or c.get("status") in ("online", "connected")]
        pick = (online or ctrls)
        if not pick:
            raise GatewayError("the admin has no machine (agent controller) registered: is Switch Console running?")
        return pick[0]
    raise GatewayError("no controllers endpoint found under /gateway")


def _bridge_name(gw: Gateway) -> str:
    bridges = items(gw.req("GET", "/collaborations"), "collaborations", "bridges")
    mm = [b for b in bridges if "mattermost" in json.dumps(b).lower()]
    pick = (mm or bridges)[0]
    return pick.get("display_name") or pick.get("name")


def step_template(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    text = build_templates.team_template()
    saved = items(gw.req("GET", "/templates"), "templates")
    if not any(t.get("name") == "crosswire-team" for t in saved):
        gw.req("POST", "/templates", {"name": "crosswire-team", "kind": "agent", "content": text,
                                      "description": "Crosswire: payco-agent, shopco-agent, mediator + the three rooms"})
        say("saved template crosswire-team to the server's Templates list")
    existing = {a.get("name") for a in items(gw.req("GET", "/agents"), "agents")}
    if {"payco-agent", "shopco-agent", "mediator"} <= existing:
        say("agents already exist; skipping the template run")
        return
    machine = _controller(gw)
    bridge = _bridge_name(gw)
    workspace = str((ROOT / "workspace").resolve())
    agents = []
    for name, playbook, sub, desc in build_templates.AGENTS:
        agents.append({"slot": name, "name": name, "description": desc, "display_name": None,
                       "instructions": (ROOT / playbook).read_text(encoding="utf-8"), "provider": "claude",
                       "machine": machine.get("id") or machine.get("controller_id"), "model": None, "advanced_config": {},
                       "isolation": "shared", "auto_mode": True, "auto_approve": False,
                       "directory": f"{workspace}/{sub}", "addressing": "owner", "can_manage_agents": False,
                       "connections": []})
    room_yaml = build_templates.rooms_yaml("payco-agent", "shopco-agent", "mediator", "notary", "priya", "sam",
                                           "payco-shopco", "payco-shopco-shared", "payco", "shopco")
    room_yaml = room_yaml.replace("channel_type:", f"bridge: {build_templates.q(bridge)}\n    channel_type:")
    out = gw.req("POST", "/rooms/from-template", {"agents": agents, "yaml": room_yaml, "inputs": {"workspace": workspace},
                                                  "template_name": "crosswire-team"})
    created = out.get("created_agents", [])
    st["agents"] = {a["name"]: a["agent_id"] for a in created}
    deaf = [a["name"] for a in created if not a.get("listening")]
    say(f"template run: created {[a['name'] for a in created]}" + (f"; not listening yet: {deaf}" if deaf else ""))


def step_rooms(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    rooms = items(gw.req("GET", "/rooms"), "rooms")
    ids = {}
    for key, name in ROOM_NAMES.items():
        match = [r for r in rooms if r.get("name") == name]
        if not match:
            raise GatewayError(f"room {name} not found (run the template step)")
        ids[key] = match[0]["id"]
    st["rooms"] = ids
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "rooms.json").write_text(json.dumps(ids, indent=1))
    subprocess.run([str(ROOT / "scripts/setup.sh")], check=True, capture_output=True)
    say(f"rooms: {ids}; workspaces re-rendered with .disclosures/rooms.json (guard rule g)")


def _mm_channel(mm: mmlib.Mattermost, name: str) -> dict[str, Any]:
    ch = mm.channel(mm.team()["id"], name)
    if not ch:
        raise GatewayError(f"{mm.me.get('username')} is not in a Mattermost channel named {name}")
    return ch


def step_claims(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    home = {"priya": "payco-internal", "sam": "shopco-internal"}
    for name in PEOPLE:
        pw = e.get(f"SWITCH_{name.upper()}_PASSWORD")
        if not pw:
            raise SystemExit(f"SWITCH_{name.upper()}_PASSWORD missing in .env (users step creates it)")
        user_gw = Gateway(e["SWITCH_BRIDGE_URL"]).login(person_email(name), pw)
        mine = user_gw.req("GET", "/auth/me/identities")
        if any(i.get("username") == name and i.get("confirmed", True) for i in items(mine, "identities")):
            say(f"claim {name}: already linked")
            continue
        mm = mmlib.Mattermost(e["MM_URL"]).login(name, e[f"MM_{name.upper()}_PASSWORD"])
        bridges = items(user_gw.req("GET", "/collaborations"), "collaborations", "bridges")
        bridge = next(b for b in bridges if "mattermost" in json.dumps(b).lower())
        claim = user_gw.req("POST", f"/collaborations/{bridge['id']}/identities",
                            {"external_user_id": mm.me["id"], "username": name})
        code = claim.get("code") or (claim.get("confirmation") or {}).get("code")
        if not code:
            raise GatewayError(f"claim for {name} returned no code (fields: {sorted(claim)})")
        ch = _mm_channel(mm, home[name])
        sent = mm.send(ch["id"], f"!link-account {code}")
        mm.wait([ch["id"]], sent["create_at"], lambda ps: bool(mmlib.real(ps)), timeout=60, quiet=3, exclude={sent["id"]})
        mine = items(user_gw.req("GET", "/auth/me/identities"), "identities")
        ok = any(i.get("username") == name for i in mine)
        say(f"claim {name}: {'linked' if ok else 'NOT confirmed'} (code posted from @{name}, never printed)")


def _rule(rooms: list[str], users: list[str], agents: list[str]) -> dict[str, Any]:
    return {"rooms": rooms, "room_groups": "*", "users": users, "agents": agents,
            "owner": False, "owner_agents": False, "platform": False}


def step_policies(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    agents = {a["name"]: a["id"] for a in items(gw.req("GET", "/agents"), "agents") if a.get("name") in AGENT_NAMES}
    missing = [n for n in AGENT_NAMES if n not in agents]
    if missing:
        raise GatewayError(f"agents missing on the server: {missing}")
    r, u = st["rooms"], st["users"]
    pay_in, shop_in, shared = r["payco-internal"], r["shopco-internal"], r["payco-shopco-shared"]
    table = {
        "payco-agent": [_rule([pay_in], [u["priya"]], []), _rule([shared], [u["priya"]], [agents["mediator"]])],
        "shopco-agent": [_rule([shop_in], [u["sam"]], []), _rule([shared], [u["sam"]], [agents["mediator"]])],
        "mediator": [_rule([shared], [u["priya"], u["sam"]], [agents["payco-agent"], agents["shopco-agent"], agents["notary"]])],
        "notary": [_rule([shared], [u["priya"], u["sam"]], [agents["mediator"]])],
    }
    POLICIES.mkdir(parents=True, exist_ok=True)
    for name, rules in table.items():
        gw.req("PUT", f"/agents/{agents[name]}/addressing-policy", {"policy": {"rules": rules}})
        back = None
        for path in (f"/agents/{agents[name]}/addressing-policy", f"/agents/{agents[name]}"):
            try:
                back = gw.req("GET", path)
                break
            except GatewayError:
                continue
        (POLICIES / f"{name}.json").write_text(json.dumps(back, indent=1, sort_keys=True) + "\n")
        say(f"policy {name}: {len(rules)} rule(s) set; read-back saved to switch/policies/{name}.json")


def _send_and_wait(mm: mmlib.Mattermost, channel: str, text: str, want: str | None, timeout: float = 180) -> list[mmlib.Post]:
    ch = _mm_channel(mm, channel)
    sent = mm.send(ch["id"], text)
    return mm.wait([ch["id"]], sent["create_at"], lambda ps: bool(mmlib.real(ps, want)), timeout=timeout,
                   exclude={sent["id"]})


def step_roles(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    priya = mmlib.Mattermost(e["MM_URL"]).login("priya", e["MM_PRIYA_PASSWORD"])
    posts = _send_and_wait(priya, "payco-shopco-shared", "!roles", None, timeout=60)
    text = " ".join(p.message for p in mmlib.real(posts))
    say("roles: " + " ".join(text.split())[:400])


def step_smoke(gw: Gateway, e: dict[str, str], st: dict[str, Any]) -> None:
    priya = mmlib.Mattermost(e["MM_URL"]).login("priya", e["MM_PRIYA_PASSWORD"])
    sam = mmlib.Mattermost(e["MM_URL"]).login("sam", e["MM_SAM_PASSWORD"])
    checks = []
    p = _send_and_wait(priya, "payco-internal", "@payco-agent hello, one line please", "payco-agent")
    checks.append(("Priya -> @payco-agent (payco-internal) answers", bool(mmlib.real(p, "payco-agent"))))
    p = _send_and_wait(sam, "payco-shopco-shared", "@payco-agent hello", "payco-agent")
    refusal = " ".join(x.message for x in mmlib.real(p, "payco-agent")).lower()
    checks.append(("Sam -> @payco-agent gets a visible refusal", any(w in refusal for w in ("not permitted", "can't act", "cannot act", "restricted"))))
    p = _send_and_wait(priya, "payco-shopco-shared", "@notary help", "notary")
    checks.append(("@notary help replies", "compare" in " ".join(x.message for x in mmlib.real(p, "notary"))))
    p = _send_and_wait(sam, "payco-shopco-shared", "@mediator who are you and what is this room for? Two lines.", "mediator")
    checks.append(("@mediator gives a room-specific answer", any(w in " ".join(x.message for x in mmlib.real(p, "mediator")).lower()
                                                                for w in ("incident", "payco", "shopco"))))
    for label, ok in checks:
        say(f"smoke: {'PASS' if ok else 'FAIL'}  {label}")
    st["smoke"] = {label: ok for label, ok in checks}


def plan() -> None:
    e = env()
    have = {k: bool(e.get(k)) for k in ("SWITCH_ADMIN_EMAIL", "SWITCH_ADMIN_PASSWORD", "SWITCH_BRIDGE_URL", "MM_URL",
                                         "MM_PRIYA_PASSWORD", "MM_SAM_PASSWORD")}
    print("credentials present in .env (values never shown):", have)
    print("steps:", " -> ".join(STEPS))
    print("template agents:", [a[0] for a in build_templates.AGENTS], "in", (ROOT / "workspace").resolve())


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "plan":
        plan()
        return 0
    steps = STEPS if argv == ["all"] else argv
    bad = [s for s in steps if s not in STEPS]
    if bad:
        raise SystemExit(f"unknown step(s) {bad}; choose from {STEPS} or 'all'")
    e = env()
    gw = admin(e)
    st = load_state()
    for s in steps:
        say(f"--- {s}")
        globals()[f"step_{s}"](gw, e, st)
        save_state(st)
    return 0 if all(st.get("smoke", {}).values()) or "smoke" not in steps else 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (GatewayError, mmlib.MMError) as exc:
        print(f"[phase7] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
