"""Raw room messages + disclosure files → one normalized event stream for the Incident Console.

This module is the Console's privacy boundary. Whatever arrives, what leaves is: who, which lane, short prose,
D-ids, field PATHS, byte LENGTHS, counts, and truncated salts/hashes. Fingerprint JSON blocks are replaced by a
count; nothing that looks like a payload value is passed on.

Raw message:  {"id", "t" (ms), "room": "payco-internal" | "payco-shopco-shared" | "shopco-internal", "sender", "body",
               "thread_id"}
Event:        {"id", "t", "kind", "lane", "who", ...kind fields}
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

LANE = {"payco-internal": "payco", "payco-shopco-shared": "shared", "shopco-internal": "shopco"}
COMPANY_OF = {"D-PAY": "payco", "D-SHOP": "shopco"}

DRAFT_RE = re.compile(r"^\s*(?:@[\w.-]+[\s,:]*)*DRAFT\s+(D-(?:PAY|SHOP)-\d+)\s*:\s*(.*)$", re.M)
HEADER_RE = re.compile(r"\[(D-(?:PAY|SHOP)-\d+)\s*[·|\-:]\s*approved by @(\w+)\]")
TYPE_RE = re.compile(r"^\s*type\s*:\s*(\w+)", re.M)
EVENT_RE = re.compile(r"^\s*event\s*:\s*(\S+)", re.M)
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n\s*```", re.S)
APPROVE_RE = re.compile(r"\b(approve|deny)\s+(D-(?:PAY|SHOP)-\d+)\b", re.I)
REFUSAL_RE = re.compile(r"not permitted to direct messages to me|my operator has restricted who can address me", re.I)
SALT_RE = re.compile(r"Salt for (INC-\d{4}):\s*`(inc-\d{4}-[0-9a-f]{8})`")
INC_OPEN_RE = re.compile(r"\b(INC-\d{4})\b.{0,40}\bopen", re.I | re.S)
DOC_RE = re.compile(r"(created|updated|deleted) room document [“\"](INC-\d{4})[”\"]")
ROW_RE = re.compile(r"^\|\s*([\w.\[\]]+)\s*\|\s*(\d+|-)\s*\|\s*(\d+|-)\s*\|\s*([+-]?\d+|-)\s*\|\s*(yes|no|-)\s*\|\s*(yes|no|-)/(yes|no|-)\s*\|", re.M)
NOTARY_HEAD_RE = re.compile(r"\*\*Notary · (D-PAY-\d+) vs (D-SHOP-\d+)\*\* · event (\S+) · salt (\S+)")
FIRST_RE = re.compile(r"First difference: ([\w.\[\]]+), delta ([+-]?\d+)")
TOTAL_RE = re.compile(r"Whole body: (\d+) vs (\d+) bytes")
CONFIRM_RE = re.compile(r"\bconfirm(ed)? root cause\b", re.I)
FIX_DONE_RE = re.compile(r"\b(PayCo|ShopCo) action item done\b", re.I)
RESOLVED_RE = re.compile(r"\bstatus[:\s*]*resolved\b|\bscorecard\b", re.I)
ROOT_AGREED_RE = re.compile(r"root[- ]cause[- ]agreed|both (?:sides|companies) (?:have )?confirmed", re.I)
PERMISSION_RE = re.compile(r"permission needed.*?request\s+`?(A\d+)`?", re.I | re.S)
HYP_ROW_RE = re.compile(r"^\|\s*(H?\d+)\s*\|\s*([^|]+?)\s*\|\s*(open|supported|ruled out|ruled-out|ruled)\s*\|\s*([^|]*?)\s*\|", re.M | re.I)
STATUS_LINE_RE = re.compile(r"^Status:\s*([\w-]+)", re.M | re.I)


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _has_non_ascii_letter(word: str) -> bool:
    import unicodedata
    return any(ord(c) > 127 and unicodedata.category(c).startswith("L") for c in word)


def who(sender: str) -> str:
    s = (sender or "").lower()
    for key in ("payco-agent", "shopco-agent", "mediator", "notary", "priya", "sam"):
        if key in s:
            return key
    return "switch" if s in ("switch-admin", "system", "admin", "switch") else s or "unknown"


def truncate_secret(value: str) -> str:
    return value if len(value) <= 12 else f"{value[:9]}…{value[-4:]}"


def prose(body: str, limit: int = 360) -> str:
    """Display text: code/JSON blocks become a count, disclosure headers and key:value lines are dropped."""
    def block(m: re.Match[str]) -> str:
        try:
            data = json.loads(m.group(1))
            n = len(data.get("fields", [])) if isinstance(data, dict) else 0
            return f"[fingerprint · {n} fields]" if n else "[structured evidence]"
        except ValueError:
            return "[code block withheld]"
    text = JSON_BLOCK_RE.sub(block, body)
    text = re.sub(r"```.*?```", "[code block withheld]", text, flags=re.S)
    text = HEADER_RE.sub(lambda m: f"{m.group(1)} (approved by {m.group(2)})", text)
    text = re.sub(r"^\s*(type|event|salt)\s*:.*$", "", text, flags=re.M)
    text = re.sub(r"\binc-\d{4}-[0-9a-f]{8}\b", lambda m: truncate_secret(m.group(0)), text)
    text = EMAIL_RE.sub("[email withheld]", text)
    text = re.sub(r"\S*[^\x00-\x7F]\S*", lambda m: m.group(0) if not _has_non_ascii_letter(m.group(0)) else "[withheld]", text)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _fingerprint_stats(body: str) -> tuple[int, int]:
    m = JSON_BLOCK_RE.search(body)
    if not m:
        return 0, 0
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return 0, 0
    if not isinstance(data, dict):
        return 0, 0
    return len(data.get("fields", []) or []), int(data.get("total_bytes") or 0)


def draft_rows(dtype: str, body: str) -> list[dict[str, Any]]:
    """What a draft card shows: labels and levels, never values."""
    n_fields, total = _fingerprint_stats(body)
    ev = (EVENT_RE.search(body) or [None, "n/a"])[1]
    if dtype.endswith("_fingerprint"):
        return [{"icon": "hash", "label": f"{ev} · {n_fields} field paths, lengths, hashes", "level": "fingerprint"},
                {"icon": "ruler", "label": "Body byte length", "level": "plain", "value": f"{total} B"},
                {"icon": "lock", "label": "Request body", "level": "withheld"}]
    if dtype in ("failure_summary", "failure_list"):
        return [{"icon": "hash", "label": "Failing event ids" if dtype == "failure_list" else "Failures by non-ASCII field",
                 "level": "fingerprint"},
                {"icon": "user", "label": "data.customer.* values", "level": "withheld"}]
    return [{"icon": "key", "label": "Spec in prose (no code)", "level": "plain", "value": dtype.replace("_", " ")},
            {"icon": "lock", "label": "Source code", "level": "withheld"}]


def parse_compare(body: str) -> dict[str, Any] | None:
    head = NOTARY_HEAD_RE.search(body)
    rows = ROW_RE.findall(body)
    if not head or not rows:
        return None
    first = FIRST_RE.search(body)
    total = TOTAL_RE.search(body)
    num = lambda x: None if x == "-" else int(x)  # noqa: E731
    return {
        "pay": head.group(1), "shop": head.group(2), "event": head.group(3), "salt": truncate_secret(head.group(4)),
        "rows": [{"path": p, "pay": num(a), "shop": num(b), "delta": num(d), "match": m == "yes",
                  "escaped_pay": ea == "yes", "escaped_shop": eb == "yes"} for p, a, b, d, m, ea, eb in rows],
        "first": first.group(1) if first else None, "first_delta": int(first.group(2)) if first else 0,
        "total_pay": int(total.group(1)) if total else None, "total_shop": int(total.group(2)) if total else None,
    }


def parse_record(content: str) -> dict[str, Any]:
    """The mediator's INC record (Markdown) → status, hypotheses. Only prose the mediator wrote; no payload values."""
    status = STATUS_LINE_RE.search(content)
    hyps = [{"id": i if i.upper().startswith("H") else f"H{i}", "title": " ".join(t.split())[:90],
             "status": "ruled" if s.lower().startswith("ruled") else s.lower(), "evidence": " ".join(e.split())[:90]}
            for i, t, s, e in HYP_ROW_RE.findall(content)]
    return {"status": status.group(1).lower() if status else None, "hypotheses": hyps}


def from_message(raw: dict[str, Any], incident: str | None) -> list[dict[str, Any]]:
    body, room = raw.get("body") or "", raw.get("room")
    base = {"id": raw["id"], "t": raw["t"], "lane": LANE.get(room), "who": who(raw.get("sender", ""))}
    out: list[dict[str, Any]] = []
    w = base["who"]

    if PERMISSION_RE.search(body):
        return [{**base, "kind": "permission_request", "req": PERMISSION_RE.search(body).group(1)}]  # type: ignore[union-attr]
    if REFUSAL_RE.search(body) and w in ("payco-agent", "shopco-agent", "mediator", "notary"):
        target = re.match(r"\s*@([\w-]+)", body)
        return [{**base, "kind": "refusal", "by": w, "to": target.group(1) if target else "?", "code": "not_permitted",
                 "text": "Switch refused a message that this agent's addressing policy does not admit."}]
    for d_id, rest in DRAFT_RE.findall(body):
        dtype = (TYPE_RE.search(body) or [None, "evidence"])[1]
        out.append({**base, "kind": "draft", "d_id": d_id, "company": COMPANY_OF[d_id.rsplit("-", 1)[0]], "dtype": dtype,
                    "title": prose(rest, 90) or dtype.replace("_", " "), "rows": draft_rows(dtype, body), "status": "awaiting"})
    if out:
        return out
    for verb, d_id in APPROVE_RE.findall(body):
        if w in ("priya", "sam"):
            out.append({**base, "kind": "approval", "d_id": d_id.upper(), "by": w, "decision": verb.lower()})
    if out:
        return out
    owner = {"D-PAY": "payco-agent", "D-SHOP": "shopco-agent"}
    headers = [(d, by) for d, by in HEADER_RE.findall(body) if owner[d.rsplit("-", 1)[0]] == w]  # quotes by others don't cross
    if headers and base["lane"] == "shared":
        dtype = (TYPE_RE.search(body) or [None, "evidence"])[1]
        n_fields, total = _fingerprint_stats(body)
        for d_id, by in headers:
            out.append({**base, "kind": "disclosure_crossed", "d_id": d_id, "company": COMPANY_OF[d_id.rsplit("-", 1)[0]],
                        "dtype": dtype, "event": (EVENT_RE.search(body) or [None, "n/a"])[1], "fields": n_fields,
                        "bytes": total, "approved_by": by, "text": prose(body)})
        return out
    if w == "notary":
        cmp_ = parse_compare(body)
        if cmp_:
            return [{**base, "kind": "notary_compare", **cmp_}]
        salt = SALT_RE.search(body)
        if salt:
            return [{**base, "kind": "salt", "incident": salt.group(1), "salt": truncate_secret(salt.group(2))}]
    doc = DOC_RE.search(body)
    if doc and w == "mediator":
        return [{**base, "kind": "record_update", "incident": doc.group(2), "action": doc.group(1)}]
    if w == "mediator" and incident is None and INC_OPEN_RE.search(body):
        out.append({**base, "kind": "incident_opened", "incident": INC_OPEN_RE.search(body).group(1)})  # type: ignore[union-attr]
    if w in ("priya", "sam") and CONFIRM_RE.search(body):
        out.append({**base, "kind": "confirmation", "by": w})
    if FIX_DONE_RE.search(body) and w in ("payco-agent", "shopco-agent"):
        out.append({**base, "kind": "fix_done", "company": FIX_DONE_RE.search(body).group(1).lower()})  # type: ignore[union-attr]
    if w == "mediator" and ROOT_AGREED_RE.search(body):
        out.append({**base, "kind": "status_change", "status": "root-cause"})
    if w == "mediator" and RESOLVED_RE.search(body):
        out.append({**base, "kind": "status_change", "status": "resolved"})
    msg = {**base, "kind": "message", "text": prose(body), "thread": bool(raw.get("thread_id"))}
    if base["lane"] == "shared" and base["who"] == "mediator":
        full = prose(body, limit=2000)   # same scrubbing, longer: the postmortem quotes the mediator's root cause and contract
        if full != msg["text"]:
            msg["full"] = full
    out.insert(0, msg)
    return out


def from_guard_log(company: str, entry: dict[str, Any], seq: int) -> dict[str, Any]:
    blocked = entry.get("decision") == "block"
    return {"id": f"guard-{company}-{seq}", "t": entry.get("t_ms", 0), "lane": company, "who": "guard",
            "kind": "guard_block" if blocked else "guard_check", "company": company,
            "rules": entry.get("rules", []), "note": entry.get("note")}


def normalize(raws: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batch helper (replay/tests): normalize messages in time order, tracking the open incident."""
    events: list[dict[str, Any]] = []
    incident: str | None = None
    for raw in sorted(raws, key=lambda r: r["t"]):
        for ev in from_message(raw, incident):
            if ev["kind"] == "incident_opened":
                incident = ev["incident"]
            events.append(ev)
    return events
