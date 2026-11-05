#!/usr/bin/env python3
"""PreToolUse guard on a company agent's Switch posts: nothing leaves the company that shouldn't.

Canonical copy: crosswire/guards/disclosure_guard.py. scripts/setup.sh copies it into each company
workspace as hooks/disclosure_guard.py. Stdlib only. Runs on mcp__switch__post_message,
send_targeted_message, create_room_document and update_room_document.

BLOCK (exit 2, a reason on stderr that says how to fix it) when the outgoing text:
  a  repo_line    has a line of 20+ chars (whitespace-normalized) found in this repo's tracked source
                  files (`git ls-files`; Markdown and lockfiles are not source). Index cached in
                  .disclosures/repo-lines.idx, rebuilt when HEAD or the working tree changes.
  b  email        contains an email address
  c  secret       contains WEBHOOK_SECRET (if set in the env) or a secret-looking token
                  (whsec_, sk-, -----BEGIN, AKIA..., ghp_..., xox?-..., Bearer <long>)
  d  non_ascii    contains non-ASCII LETTERS (Unicode category L*): in this domain, customer names
  e  unapproved   looks like a disclosure (a "[D-… · approved by @…]" header or a disclosure type line)
                  whose D-id isn't "approved" in .disclosures/ledger.jsonl (latest status wins).
                  A post that starts with "DRAFT D-PAY-<n>:" / "DRAFT D-SHOP-<n>:" is a draft for the
                  internal room and is allowed (logged as a draft).
  f  room_doc     uses create_room_document / update_room_document (only the mediator writes those)
  g  room         is a DRAFT while the session is NOT in the company's private room. The current room is
                  recorded by this script's --track-room mode (a PreToolUse hook on connect_to_room) and
                  cleared by --session-start (a SessionStart hook), so it is never stale; room ids are
                  classified by .disclosures/rooms.json {"private": "<id>", "shared": "<id>"} (written in
                  Phase 7). Unknown room = not private, so drafts fail closed.

Every decision is appended to .disclosures/guard.log.jsonl: ts, tool, decision, rule(s), length, and for an allowed
disclosure the D-id and evidence digest the approver signed. The log is hash-chained (ledger_chain.py); `just
verify-ledger` checks the chain and that every disclosure it allowed has a matching signed approval.
Never the text itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

POST_TOOLS = {"mcp__switch__post_message", "mcp__switch__send_targeted_message"}
DOC_TOOLS = {"mcp__switch__create_room_document", "mcp__switch__update_room_document"}
TEXT_KEYS = ("body", "content", "caption", "name", "description", "instructions")
MIN_LINE = 20
NOT_SOURCE = re.compile(r"(\.md$|(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock)$)")
MAX_FILE_BYTES = 1_000_000

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
SECRET_RES = [
    re.compile(r"whsec_[A-Za-z0-9]{4,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bgh[ousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{8,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),          # JWT
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@]+:[^\s@/]{4,}@"),                                 # URL with a password
    # a credential assigned to a key/secret/token/password name (KEY=..., "api_key": "...", password: ...)
    re.compile(r"(?i)\b[\w-]*(?:secret|passw(?:or)?d|api[_-]?key|access[_-]?key|auth[_-]?token|private[_-]?key)[\w-]*"
               r"[\"']?\s*[:=]\s*[\"']?(?![\"']?\s*(?:<|\$\{|\*{3}|x{4}|redacted|none|null|\.\.\.))[^\s\"',;]{8,}"),
]
CODE_TOKEN_RE = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|`[^`]*`|[A-Za-z_$][A-Za-z0-9_$]*|\d+(?:\.\d+)?"
                           r"|===|!==|==|!=|<=|>=|=>|->|\*\*|&&|\|\||\?\?|[^\sA-Za-z0-9_$]")
KEYWORDS = frozenset("""def class return if elif else for while in not and or is None True False import from as with try
except finally raise lambda yield await async pass break continue global nonlocal assert del const let var function
new this typeof instanceof null undefined true false export default require module throw catch switch case of void
super extends static get set""".split())
NAME_TOKEN_RE = re.compile(r"\b[A-Z][a-z]{2,}\b")
DISCLOSURE_TYPES = ("delivery_fingerprint", "verification_fingerprint", "failure_summary", "failure_list",
                    "signing_spec", "verification_spec")
DISCLOSURE_HEADER_RE = re.compile(r"\[(D-(?:PAY|SHOP)-\d+)\s*[·|\-:]\s*approved by @([A-Za-z0-9._-]+)\]")
TYPE_LINE_RE = re.compile(r"^\s*type\s*:\s*(" + "|".join(DISCLOSURE_TYPES) + r")\b", re.M)
D_ID_RE = re.compile(r"\bD-(?:PAY|SHOP)-\d+\b")
DRAFT_RE = re.compile(r"^\s*(?:@[\w.-]+[\s,:]*)*DRAFT\s+(D-(?:PAY|SHOP)-\d+)\s*:")   # leading @mentions allowed
DRAFT_WORD_RE = re.compile(r"^\s*(?:@[\w.-]+[\s,:]*)*DRAFT\b", re.I)

FIX = {
    "unsigned": "the approver has no signed approval for it (or it was denied, or the approver can't be reached). "
                "A disclosure crosses only after the owner replies `approve D-…` to your DRAFT in your private room; "
                "the approver records that. Wait for it, then post the approved block unchanged",
    "changed": "its evidence (type/event/salt/JSON) differs from the draft the owner approved. Post the approved "
               "block exactly as drafted, or post a new DRAFT and ask for approval again",
    "prose": "a disclosure post may contain only the approved evidence block: the [D-… · approved by @…] header, "
             "the type/event/salt lines and the JSON, plus an optional leading @mention. Put any explanation in a "
             "separate message",
    "repo_line": "it contains a line of this repository's source code. Share evidence (fingerprints, counts, "
                 "specs in your own words), never code",
    "email": "it contains an email address. Remove it",
    "customer_name": "it contains a customer's name. Use event ids or customer ids, never names",
    "secret": "it contains a secret or credential. Remove it and never post secrets",
    "non_ascii": "it contains non-ASCII letters, which here means customer data. Posts must be plain ASCII; "
                 "use event ids, never names",
    "unapproved": "it looks like a disclosure that isn't approved in .disclosures/ledger.jsonl. Post a "
                  "'DRAFT D-…:' in your internal room, wait for the owner's 'approve D-…', record it in the "
                  "ledger, then post it",
    "room_doc": "company agents never create or edit room documents; only the mediator does. Ask the mediator",
    "room": "drafts go only in your company's private room. Call connect_to_room with your internal room's id "
            "(from list_rooms) first; never post a draft in the shared room",
}


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent).resolve()


def disclosures_dir(root: Path) -> Path:
    d = root / ".disclosures"
    d.mkdir(exist_ok=True)
    return d


def norm(line: str) -> str:
    return " ".join(line.split())


def shape(line: str) -> str | None:
    """A code line with every identifier replaced: the same code with renamed variables or different spacing has
    the same shape. None for lines too generic to match on (few tokens, or hardly any punctuation/literals)."""
    toks = CODE_TOKEN_RE.findall(line)
    if len(toks) < 8:
        return None
    out, ident, other = [], 0, 0
    for tk in toks:
        if (tk[0].isalpha() or tk[0] in "_$") and tk not in KEYWORDS:
            out.append("§")
            ident += 1
        else:
            out.append(tk)
            other += tk not in KEYWORDS
    return " ".join(out) if ident and other >= 4 else None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def repo_lines(root: Path) -> set[str]:
    try:
        head = _git(root, "rev-parse", "HEAD").strip()
        status = _git(root, "status", "--porcelain=v1")
        files = [f for f in _git(root, "ls-files").splitlines() if f and not NOT_SOURCE.search(f)]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    key = hashlib.sha256((head + "\0" + status).encode()).hexdigest()
    idx = disclosures_dir(root) / "repo-lines.idx"
    if idx.exists():
        try:
            cached = json.loads(idx.read_text())
            if cached.get("key") == key and "shapes" in cached:
                SHAPES.update(cached["shapes"])
                return set(cached["lines"])
        except (ValueError, KeyError):
            pass
    lines: set[str] = set()
    shapes: set[str] = set()
    for rel in files:
        path = root / rel
        try:
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for raw in text.splitlines():
            n = norm(raw)
            if len(n) >= MIN_LINE:
                lines.add(n)
                s = shape(n)
                if s:
                    shapes.add(s)
    idx.write_text(json.dumps({"key": key, "lines": sorted(lines), "shapes": sorted(shapes)}))
    SHAPES.update(shapes)
    return lines


SHAPES: set[str] = set()   # filled by repo_lines()


def customer_name_hashes(root: Path) -> set[str]:
    """sha256 of each lower-cased ASCII customer name token (`just setup` writes them; names never sit in plain text)."""
    try:
        return set(json.loads((root / ".disclosures" / "customer-names.json").read_text())["tokens"])
    except (OSError, ValueError, KeyError, TypeError):
        return set()


def names_customer(text: str, hashes: set[str]) -> bool:
    """Two adjacent capitalised words that are both customer name tokens ("Alice Smith", "Smith, Alice")."""
    if not hashes:
        return False
    h = lambda w: hashlib.sha256(w.lower().encode()).hexdigest()  # noqa: E731
    words = [(m.group(0), m.end()) for m in NAME_TOKEN_RE.finditer(text)]
    for (a, end), (b, _e) in zip(words, words[1:]):
        gap = text[end:text.index(b, end)]
        if len(gap) <= 3 and gap.strip(" ,") == "" and h(a) in hashes and h(b) in hashes:
            return True
    return False


def approved_ids(root: Path) -> set[str]:
    """Approved D-ids: one .disclosures/approvals/<D-id>.json per decision (written with the Write tool, so no shell
    is needed), plus the older append-only .disclosures/ledger.jsonl. The latest decision per id wins."""
    ledger = root / ".disclosures" / "ledger.jsonl"
    latest: dict[str, tuple[str, str]] = {}
    for f in sorted((root / ".disclosures" / "approvals").glob("D-*.json")):
        try:
            entry = json.loads(f.read_text(encoding="utf-8"))
            d_id = str(entry.get("id") or f.stem)
            if d_id == f.stem:
                latest[d_id] = (str(entry.get("ts", "")), str(entry.get("status", "")))
        except (OSError, ValueError, AttributeError):
            continue
    if ledger.exists():
        for raw in ledger.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(raw)
                ts, d_id = str(entry.get("ts", "")), str(entry["id"])
                if d_id not in latest or ts >= latest[d_id][0]:
                    latest[d_id] = (ts, str(entry.get("status", "")))
            except (ValueError, KeyError, TypeError):
                continue
    return {d for d, (_ts, status) in latest.items() if status == "approved"}


def current_room(root: Path) -> str | None:
    f = root / ".disclosures" / "current_room"
    return f.read_text().strip() or None if f.exists() else None


def room_kind(root: Path) -> str:
    room = current_room(root)
    try:
        rooms = json.loads((root / ".disclosures" / "rooms.json").read_text())
    except (OSError, ValueError):
        rooms = {}
    if room and room == rooms.get("private"):
        return "private"
    if room and room == rooms.get("shared"):
        return "shared"
    return "unknown"


def outgoing_text(tool_input: dict) -> str:
    parts = [tool_input[k] for k in TEXT_KEYS if isinstance(tool_input.get(k), str)]
    return "\n".join(parts)


def _strip_md(line: str) -> str:
    return norm(line).strip("`*_>-#|~ ").strip()


def check(tool: str, text: str, root: Path) -> list[str]:
    rules: list[str] = []
    if tool in DOC_TOOLS:
        rules.append("room_doc")

    index = repo_lines(root)
    if index:
        for line in text.splitlines():
            candidates = {norm(line), _strip_md(line)}
            if any(len(c) >= MIN_LINE and (c in index or any(r in c for r in index if len(r) >= MIN_LINE and len(r) <= len(c)))
                   for c in candidates) or any(shape(c) in SHAPES for c in candidates if shape(c)):
                rules.append("repo_line")
                break

    if names_customer(text, customer_name_hashes(root)):
        rules.append("customer_name")

    if EMAIL_RE.search(text):
        rules.append("email")

    secret = os.environ.get("WEBHOOK_SECRET")
    if (secret and len(secret) >= 8 and secret in text) or any(r.search(text) for r in SECRET_RES):
        rules.append("secret")

    if any(ord(ch) > 127 and unicodedata.category(ch).startswith("L") for ch in text):
        rules.append("non_ascii")

    draft = DRAFT_RE.match(text)
    if (draft or DRAFT_WORD_RE.match(text)) and room_kind(root) != "private":
        rules.append("room")
    looks_like_disclosure = DISCLOSURE_HEADER_RE.search(text) or TYPE_LINE_RE.search(text)
    if looks_like_disclosure and not draft:
        ids = {m.group(1) for m in DISCLOSURE_HEADER_RE.finditer(text)} or set(D_ID_RE.findall(text))
        if APPROVER_URL:
            rules += approver_problems(text, ids)
        elif not ids or not ids <= approved_ids(root):
            rules.append("unapproved")
    return rules


def _arg(flag: str) -> str | None:
    args = sys.argv[1:]
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


APPROVER_URL = _arg("--approver")   # http://127.0.0.1:7400 in the rendered settings; absent = legacy approval files
VERIFIED: list[dict] = []           # disclosures the approver's signature covered in this post (logged on allow)


def approver_problems(text: str, ids: set[str]) -> list[str]:
    """A disclosure crosses only with the approver's signed record, matching evidence, and no unapproved prose."""
    import urllib.request
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import disclosure_canon as canon
    import ed25519_verify
    if not ids:
        return ["unsigned"]
    problems: list[str] = []
    try:
        with urllib.request.urlopen(APPROVER_URL.rstrip("/") + "/pubkey", timeout=4) as r:
            pub = bytes.fromhex(json.loads(r.read())["ed25519"])
    except Exception:  # noqa: BLE001  fail closed: no approver, no disclosures
        return ["unsigned"]
    for d_id in sorted(ids):
        try:
            with urllib.request.urlopen(APPROVER_URL.rstrip("/") + f"/approval/{d_id}", timeout=4) as r:
                rec = json.loads(r.read())
        except Exception:  # noqa: BLE001
            problems.append("unsigned")
            continue
        sig = bytes.fromhex(rec.pop("sig", "") or "00")
        payload = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()
        if not ed25519_verify.verify(pub, payload, sig) or rec.get("status") != "approved" or rec.get("d_id") != d_id:
            problems.append("unsigned")
            continue
        blk = canon.block(text, d_id)
        if not blk or canon.digest(blk) != rec.get("sha256"):
            problems.append("changed")
        else:
            VERIFIED.append({"d_id": d_id, "sha256": rec["sha256"], "incident": rec.get("incident")})
    if canon.extra_prose(text):
        problems.append("prose")
    return sorted(set(problems))


def log(root: Path, tool: str, decision: str, rules: list[str], length: int, note: str | None = None) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ledger_chain
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": tool, "decision": decision,
             "rules": rules, "length": length}
    if note:
        entry["note"] = note
    if decision == "allow" and VERIFIED:
        entry["disclosures"] = VERIFIED
    ledger_chain.append(disclosures_dir(root) / "guard.log.jsonl", entry)


def integrity_problem(root: Path) -> str | None:
    """Compare the project's pinned control files (switch/state/pins.json, written by `just setup`) with what's there."""
    args = sys.argv[1:]
    if "--pins" not in args or args.index("--pins") + 1 >= len(args):
        return None
    try:
        pins = json.loads(Path(args[args.index("--pins") + 1]).read_text(encoding="utf-8")).get(str(root))
    except (OSError, ValueError):
        return "integrity pins are unreadable"
    if not pins:
        return "no integrity pins for this project"
    for rel, digest in pins.get("files", {}).items():
        f = root / rel
        if (hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else "missing") != digest:
            return f"integrity check failed: {rel} differs from the pinned copy"
    return None


def main() -> int:
    root = project_dir()
    tool = "?"
    if "--session-start" in sys.argv[1:]:
        (disclosures_dir(root) / "current_room").unlink(missing_ok=True)
        return 0
    if "--track-room" in sys.argv[1:]:
        try:
            room = (json.loads(sys.stdin.read()).get("tool_input") or {}).get("room_id")
        except (ValueError, AttributeError):
            room = None
        f = disclosures_dir(root) / "current_room"
        if isinstance(room, str) and room:
            f.write_text(room)
        else:
            f.unlink(missing_ok=True)      # can't tell where we're going: forget where we were
        return 0
    try:
        event = json.loads(sys.stdin.read())
        tool = str(event["tool_name"])
        tool_input = event.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            raise ValueError("tool_input is not an object")
    except (ValueError, KeyError, TypeError) as exc:
        log(root, tool, "block", ["unparseable"], 0)
        print(f"disclosure_guard: could not read the hook input ({exc}); blocking", file=sys.stderr)
        return 2
    if tool not in POST_TOOLS | DOC_TOOLS:
        return 0
    bad = integrity_problem(root)
    if bad:  # fail closed: a changed guard, settings file or playbook means nothing is posted until `just setup`
        log(root, tool, "block", ["integrity"], 0)
        print(f"disclosure_guard: {bad}; nothing can be posted until `just setup` re-installs the controls", file=sys.stderr)
        return 2
    text = outgoing_text(tool_input)
    rules = check(tool, text, root)
    if rules:
        log(root, tool, "block", rules, len(text))
        reasons = "; ".join(f"[{r}] {FIX[r]}" for r in rules)
        print(f"disclosure_guard: blocked {tool.rsplit('__', 1)[-1]}: {reasons}. Do not try to rephrase around this.",
              file=sys.stderr)
        return 2
    log(root, tool, "allow", [], len(text), f"draft in {room_kind(root)} room" if DRAFT_RE.match(text) else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
