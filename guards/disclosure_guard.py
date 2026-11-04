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

Every decision is appended to .disclosures/guard.log.jsonl: ts, tool, decision, rule(s), length.
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
]
DISCLOSURE_TYPES = ("delivery_fingerprint", "verification_fingerprint", "failure_summary", "failure_list",
                    "signing_spec", "verification_spec")
DISCLOSURE_HEADER_RE = re.compile(r"\[(D-(?:PAY|SHOP)-\d+)\s*[·|\-:]\s*approved by @([A-Za-z0-9._-]+)\]")
TYPE_LINE_RE = re.compile(r"^\s*type\s*:\s*(" + "|".join(DISCLOSURE_TYPES) + r")\b", re.M)
D_ID_RE = re.compile(r"\bD-(?:PAY|SHOP)-\d+\b")
DRAFT_RE = re.compile(r"^\s*DRAFT\s+(D-(?:PAY|SHOP)-\d+)\s*:")

FIX = {
    "repo_line": "it contains a line of this repository's source code. Share evidence (fingerprints, counts, "
                 "specs in your own words), never code",
    "email": "it contains an email address. Remove it",
    "secret": "it contains a secret or credential. Remove it and never post secrets",
    "non_ascii": "it contains non-ASCII letters, which here means customer data. Posts must be plain ASCII; "
                 "use event ids, never names",
    "unapproved": "it looks like a disclosure that isn't approved in .disclosures/ledger.jsonl. Post a "
                  "'DRAFT D-…:' in your internal room, wait for the owner's 'approve D-…', record it in the "
                  "ledger, then post it",
    "room_doc": "company agents never create or edit room documents; only the mediator does. Ask the mediator",
}


def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parent.parent).resolve()


def disclosures_dir(root: Path) -> Path:
    d = root / ".disclosures"
    d.mkdir(exist_ok=True)
    return d


def norm(line: str) -> str:
    return " ".join(line.split())


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
            if cached.get("key") == key:
                return set(cached["lines"])
        except (ValueError, KeyError):
            pass
    lines: set[str] = set()
    for rel in files:
        path = root / rel
        try:
            if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines.update(n for n in (norm(l) for l in text.splitlines()) if len(n) >= MIN_LINE)
    idx.write_text(json.dumps({"key": key, "lines": sorted(lines)}))
    return lines


def approved_ids(root: Path) -> set[str]:
    ledger = root / ".disclosures" / "ledger.jsonl"
    latest: dict[str, str] = {}
    if ledger.exists():
        for raw in ledger.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(raw)
                latest[str(entry["id"])] = str(entry.get("status", ""))
            except (ValueError, KeyError, TypeError):
                continue
    return {d for d, status in latest.items() if status == "approved"}


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
                   for c in candidates):
                rules.append("repo_line")
                break

    if EMAIL_RE.search(text):
        rules.append("email")

    secret = os.environ.get("WEBHOOK_SECRET")
    if (secret and len(secret) >= 8 and secret in text) or any(r.search(text) for r in SECRET_RES):
        rules.append("secret")

    if any(ord(ch) > 127 and unicodedata.category(ch).startswith("L") for ch in text):
        rules.append("non_ascii")

    draft = DRAFT_RE.match(text)
    looks_like_disclosure = DISCLOSURE_HEADER_RE.search(text) or TYPE_LINE_RE.search(text)
    if looks_like_disclosure and not draft:
        ids = {m.group(1) for m in DISCLOSURE_HEADER_RE.finditer(text)} or set(D_ID_RE.findall(text))
        if not ids or not ids <= approved_ids(root):
            rules.append("unapproved")
    return rules


def log(root: Path, tool: str, decision: str, rules: list[str], length: int, note: str | None = None) -> None:
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": tool, "decision": decision,
             "rules": rules, "length": length}
    if note:
        entry["note"] = note
    with (disclosures_dir(root) / "guard.log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def main() -> int:
    root = project_dir()
    tool = "?"
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
    text = outgoing_text(tool_input)
    rules = check(tool, text, root)
    if rules:
        log(root, tool, "block", rules, len(text))
        reasons = "; ".join(f"[{r}] {FIX[r]}" for r in rules)
        print(f"disclosure_guard: blocked {tool.rsplit('__', 1)[-1]}: {reasons}. Do not try to rephrase around this.",
              file=sys.stderr)
        return 2
    log(root, tool, "allow", [], len(text), "draft" if DRAFT_RE.match(text) else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
