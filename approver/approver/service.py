"""The approver: the only thing that can turn a human's "approve D-…" into an approval the guard accepts.

Runs in Docker. Holds an Ed25519 signing key in a Docker volume (never on the host filesystem) and the canonical pins
of every agent's controls (computed at start from a read-only mount of the workspaces). It watches the two private
Mattermost channels and accepts approvals only from Priya's (PayCo) and Sam's (ShopCo) Mattermost user ids. For each
one it finds the latest draft that company's agent posted in that channel and signs

    {d_id, incident, sha256 of the draft's canonical evidence, approver, approver_user_id, draft/approval post ids, time}

It refuses to sign while any workspace control differs from its pins, and binds every approval to the CURRENT incident:
it also watches the shared room for the notary's `Salt for INC-nnnn: ...` replies, and signs (and later serves) a record
only while its incident is the latest one the notary issued a salt for and its salt is the one the notary issued for it.
An approval from an earlier incident, or a draft with a made-up or rotated-out salt, is never accepted. The disclosure guard fetches the record at
posting time (GET /approval/<d_id>), verifies the signature and compares the evidence hash with what is being posted.

Every signed decision is also appended to approvals.jsonl in the volume, hash-chained (ledger_chain.py) with the
chain link inside the signature, and served read-only at GET /ledger for `just verify-ledger`.

    GET /health   GET /pubkey   GET /approval/<d_id>   GET /pins   GET /ledger
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent))
import disclosure_canon as canon  # noqa: E402  (copied from guards/ at build time)
import ledger_chain  # noqa: E402  (copied from guards/ at build time)

DATA = Path(os.environ.get("APPROVER_DATA", "/data"))
WS = Path(os.environ.get("APPROVER_WS", "/ws"))
PORT = int(os.environ.get("APPROVER_PORT", "7400"))
CONTROLS = ("hooks/path_guard.py", "hooks/disclosure_guard.py", "hooks/disclosure_canon.py", "hooks/ed25519_verify.py", "hooks/ledger_chain.py",
            ".claude/settings.json", ".mcp.json", "CLAUDE.md", "AGENTS.md", ".disclosures/rooms.json", ".disclosures/customer-names.json", "bin/test", "bin/sandbox-check")
COMPANY = {"payco-internal": ("priya", "payco-agent", "D-PAY"), "shopco-internal": ("sam", "shopco-agent", "D-SHOP")}
APPROVE_RE = re.compile(r"\b(approve|deny)\s+(D-(?:PAY|SHOP)-\d+)\b", re.I)
SHARED = "payco-shopco-shared"
SALT_POST_RE = re.compile(r"Salt for (INC-\d{4}):\s*`([^`\s]+)`")


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} approver: {msg}", flush=True)


# ------------------------------------------------------------------ key and pins

def load_key() -> Ed25519PrivateKey:
    DATA.mkdir(parents=True, exist_ok=True)
    f = DATA / "approver.key"
    if f.exists():
        return serialization.load_pem_private_key(f.read_bytes(), password=None)  # type: ignore[return-value]
    k = Ed25519PrivateKey.generate()
    f.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.chmod(f, 0o600)
    log("generated a new signing key (kept in the approver's volume)")
    return k


def workspace_hashes() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for agent in ("payco", "shopco", "mediator"):
        d = WS / agent
        out[agent] = {rel: hashlib.sha256((d / rel).read_bytes()).hexdigest() for rel in CONTROLS if (d / rel).is_file()}
    return out


# ------------------------------------------------------------------ Mattermost (read-only)

class MM:
    def __init__(self, url: str, user: str, password: str) -> None:
        u = urllib.parse.urlparse(url)
        host = u.hostname if u.hostname not in ("localhost", "127.0.0.1") else "host.docker.internal"
        self.base = f"{u.scheme}://{host}:{u.port}/api/v4"
        self.token = ""
        r = self._req("POST", "/users/login", {"login_id": user, "password": password}, raw=True)
        self.token = r.headers.get("Token", "")

    def _req(self, method: str, path: str, body=None, raw: bool = False):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Requested-With", "XMLHttpRequest")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        resp = urllib.request.urlopen(req, timeout=20)
        return resp if raw else json.loads(resp.read() or b"null")

    def get(self, path: str):
        return self._req("GET", path)


# ------------------------------------------------------------------ the approver

class Approver:
    def __init__(self) -> None:
        self.key = load_key()
        self.pub = self.key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.pins = workspace_hashes()
        self.records: dict[str, dict] = {}
        self.refusals: list[dict] = []
        self.current: str | None = None          # the incident the notary most recently issued a salt for
        self.issued: dict[str, str] = {}         # incident -> the salt the notary issued for it (latest)
        self.lock = threading.Lock()
        log(f"pinned {sum(len(v) for v in self.pins.values())} control files across {len(self.pins)} workspaces")

    def integrity_problem(self) -> str | None:
        now = workspace_hashes()
        for agent, files in self.pins.items():
            for rel, digest in files.items():
                if now.get(agent, {}).get(rel) != digest:
                    return f"{agent}/{rel} differs from the approver's pins"
        return None

    def on_salt(self, incident: str, salt: str) -> None:
        with self.lock:
            changed = (self.current, self.issued.get(incident)) != (incident, salt)
            self.issued[incident], self.current = salt, incident
        if changed:
            log(f"current incident {incident} (salt issued by the notary)")

    def binding_problem(self, incident: str | None, salt: str | None) -> str | None:
        """None if (incident, salt) is the current incident and the salt the notary issued for it."""
        if self.current is None:
            return "no incident salt issued by the notary yet"
        if incident != self.current:
            return f"incident {incident} is not the current incident {self.current}"
        if salt != self.issued.get(incident):
            return f"salt {salt} was not issued by the notary for {incident}"
        return None

    def servable(self, d_id: str) -> dict | None:
        rec = self.records.get(d_id)
        if rec and self.binding_problem(rec.get("incident"), rec.get("salt")) is None:
            return rec
        return None

    def sign(self, record: dict) -> dict:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        return {**record, "sig": self.key.sign(payload).hex()}

    def on_approval(self, channel: str, decision: str, d_id: str, approval: dict, draft: dict | None, user: str) -> None:
        bad = self.integrity_problem()
        if bad:
            self.refusals.append({"d_id": d_id, "reason": bad, "at": approval["create_at"]})
            log(f"refused to sign {d_id}: {bad}")
            return
        if draft is None:
            self.refusals.append({"d_id": d_id, "reason": "no draft of that id in the private room", "at": approval["create_at"]})
            log(f"refused to sign {d_id}: no draft found")
            return
        blk = canon.block(draft["message"], d_id)
        salt = canon.canonical(blk).get("salt") if blk else None
        stale = self.binding_problem(canon.incident_of(blk) if blk else None, salt)
        if stale:
            self.refusals.append({"d_id": d_id, "reason": stale, "at": approval["create_at"]})
            log(f"refused to sign {d_id}: {stale}")
            return
        record = {"v": 1, "d_id": d_id, "status": "approved" if decision == "approve" else "denied",
                  "incident": canon.incident_of(blk) if blk else None, "salt": salt, "sha256": canon.digest(blk) if blk else None,
                  "approver": user, "approver_user_id": approval["user_id"], "draft_post_id": draft["id"],
                  "approval_post_id": approval["id"], "approved_at": datetime.fromtimestamp(approval["create_at"] / 1000, timezone.utc).isoformat()}
        def finalize(e: dict) -> dict:          # the chain link (prev) is part of what is signed
            return self.sign({k: v for k, v in e.items() if k != "sig"})
        signed = ledger_chain.append(DATA / "approvals.jsonl", record, finalize)
        signed = {k: v for k, v in signed.items() if k != "h"}
        with self.lock:
            self.records[d_id] = signed
        log(f"{record['status']} {d_id} for {record['incident']} by {user} (evidence {str(record['sha256'])[:12]}…)")


def watch(ap: Approver, mm: MM) -> None:
    team = mm.get("/users/me/teams")[0]["id"]
    users = {n: mm.get(f"/users/username/{n}")["id"] for n in ("priya", "sam", "payco-agent", "shopco-agent", "notary")}
    chans = {name: mm.get(f"/teams/{team}/channels/name/{name}")["id"] for name in COMPANY}
    shared = mm.get(f"/teams/{team}/channels/name/{SHARED}")["id"]
    since = {c: int(time.time() * 1000) for c in chans.values()}
    seen: set[str] = set()

    def salts(posts: list[dict]) -> None:   # only the notary's own account can name the current incident
        for p in sorted(posts, key=lambda q: q["create_at"]):
            m = SALT_POST_RE.search(p.get("message", ""))
            if m and p["user_id"] == users["notary"]:
                ap.on_salt(m.group(1).upper(), m.group(2))

    hist = mm.get(f"/channels/{shared}/posts?per_page=200") or {}     # recover the current incident after a restart
    salts(list((hist.get("posts") or {}).values()))
    shared_since = max([p["create_at"] for p in (hist.get("posts") or {}).values()] or [int(time.time() * 1000)])
    log(f"watching {', '.join(chans)} for approvals from priya and sam; {SHARED} for the notary's incident salts")
    while True:
        try:
            data = mm.get(f"/channels/{shared}/posts?since={shared_since - 1}&collapsedThreads=false") or {}
            posts = list((data.get("posts") or {}).values())
            salts(posts)
            shared_since = max([shared_since] + [p["create_at"] for p in posts])
        except (urllib.error.URLError, OSError) as exc:
            log(f"mattermost: {exc}")
        for name, cid in chans.items():
            human, agent, prefix = COMPANY[name]
            try:
                data = mm.get(f"/channels/{cid}/posts?since={since[cid] - 1}&collapsedThreads=false") or {}
            except (urllib.error.URLError, OSError) as exc:
                log(f"mattermost: {exc}")
                continue
            posts = sorted((data.get("posts") or {}).values(), key=lambda p: p["create_at"])
            for p in posts:
                since[cid] = max(since[cid], p["create_at"])
                if p["id"] in seen or p.get("type", "").startswith("system_"):
                    continue
                seen.add(p["id"])
                m = APPROVE_RE.search(p.get("message", ""))
                if not m or p["user_id"] != users[human] or not m.group(2).upper().startswith(prefix):
                    continue           # only Priya (PayCo) and Sam (ShopCo), each for their own company's drafts
                d_id = m.group(2).upper()
                hist = mm.get(f"/channels/{cid}/posts?per_page=200") or {}
                drafts = [q for q in (hist.get("posts") or {}).values()
                          if q["user_id"] == users[agent] and q["create_at"] < p["create_at"]
                          and re.match(rf"\s*DRAFT {re.escape(d_id)}\b", q.get("message", "")) and canon.block(q["message"], d_id)]
                draft = max(drafts, key=lambda q: q["create_at"]) if drafts else None
                ap.on_approval(name, m.group(1).lower(), d_id, p, draft, human)
        time.sleep(2)


def serve(ap: Approver) -> None:
    class H(BaseHTTPRequestHandler):
        def _json(self, code: int, body) -> None:
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/health":
                self._json(200, {"ok": True, "pins": sum(len(v) for v in ap.pins.values()), "approvals": len(ap.records),
                                 "integrity": ap.integrity_problem() or "ok", "refusals": len(ap.refusals),
                                 "incident": ap.current})
            elif path == "/pubkey":
                self._json(200, {"ed25519": ap.pub.hex()})
            elif path == "/pins":
                self._json(200, ap.pins)
            elif path == "/ledger":
                f = DATA / "approvals.jsonl"
                self._json(200, {"lines": f.read_text(encoding="utf-8").splitlines() if f.exists() else []})
            elif path.startswith("/approval/"):
                d_id = path.rsplit("/", 1)[1].upper()
                rec = ap.servable(d_id)          # never an approval from another incident or for a rotated-out salt
                self._json(200 if rec else 404, rec or {"error": "no signed approval for that id in the current incident"
                                                        if d_id in ap.records else "no signed approval for that id"})
            else:
                self._json(404, {"error": "not found"})

        def log_message(self, *a) -> None:  # quiet
            pass

    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()


def main() -> None:
    ap = Approver()
    mm = MM(os.environ["MM_URL"], os.environ["MM_USER"], os.environ["MM_PASSWORD"])
    threading.Thread(target=watch, args=(ap, mm), daemon=True).start()
    log(f"listening on :{PORT}")
    serve(ap)


if __name__ == "__main__":
    main()
