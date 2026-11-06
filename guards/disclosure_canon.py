"""The canonical form of a disclosure: what a human approves and what the approver signs.

Shared by the approver service (which signs) and disclosure_guard (which checks at posting time). Stdlib only.

A disclosure block starts at its header `[D-PAY-3 · approved by @priya]` and carries `type:`, `event:` and `salt:` lines
and JSON code blocks. The canonical form is the header's D-id, those three fields and every JSON block re-serialized
with sorted keys: all the evidence that crosses, and nothing about how it was laid out. Prose is not part of it, so a
disclosure *post* may contain only the evidence block (see `extra_prose`): explanations go in a separate message.
"""
from __future__ import annotations

import hashlib
import json
import re

HEADER = re.compile(r"\[(D-(?:PAY|SHOP)-\d+)\s*[·|\-:]\s*approved by @([A-Za-z0-9._-]+)\]")
FIELD = re.compile(r"^\s*(type|event|salt)\s*:\s*(\S+)\s*$", re.M)
FENCE = re.compile(r"```[^\n`]*\n?(.*?)```", re.S)   # fallback only: see fences()
_DECODER = json.JSONDecoder()


def fences(text: str) -> list[tuple[int, int, str]]:
    """(start, end, content) of each fenced block. A JSON block is decoded in full before its closing fence is looked
    for, so backticks inside JSON strings (a docs excerpt with its own ``` fences) can't end the block early."""
    out, i = [], 0
    while True:
        p = text.find("```", i)
        if p < 0:
            return out
        if p > 0 and text[p - 1] not in " \t\n":     # only a fence at a line start or after whitespace opens a block
            i = p + 3
            continue
        q = p + 3
        while q < len(text) and text[q] not in "\n" and not text[q].isspace() and text[q] not in "{[`":
            q += 1                                     # the language tag (json, text, ...)
        j = q
        while j < len(text) and text[j].isspace():
            j += 1
        if j < len(text) and text[j] in "{[":
            try:
                _obj, k = _DECODER.raw_decode(text, j)
                m = k
                while m < len(text) and text[m].isspace():
                    m += 1
                if text.startswith("```", m):
                    out.append((p, m + 3, text[j:k]))
                    i = m + 3
                    continue
            except ValueError:
                pass
        e = text.find("```", q)
        if e < 0:
            out.append((p, len(text), text[q:]))
            return out
        out.append((p, e + 3, text[q:e]))
        i = e + 3
MENTION_LINE = re.compile(r"^\s*(?:@[\w.-]+[\s,:]*)+$")
SALT_INCIDENT = re.compile(r"^(inc-\d{4})-[0-9a-z]+$", re.I)


def block(text: str, d_id: str | None = None) -> str | None:
    """The disclosure block for d_id (or the first one): from its header to the next header or the end."""
    heads = list(HEADER.finditer(text or ""))
    for i, m in enumerate(heads):
        if d_id is None or m.group(1) == d_id:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            return text[m.start():end]
    return None


def canonical(blk: str) -> dict:
    head = HEADER.search(blk)
    fields = {k: v for k, v in FIELD.findall(blk)}
    blocks = []
    for _s, _e, raw in fences(blk):
        try:
            blocks.append(json.dumps(json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        except ValueError:
            blocks.append(" ".join(raw.split()))
    return {"d_id": head.group(1) if head else None, "type": fields.get("type"), "event": fields.get("event"),
            "salt": fields.get("salt"), "json": blocks}


def digest(blk: str) -> str:
    return hashlib.sha256(json.dumps(canonical(blk), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def incident_of(blk: str) -> str | None:
    """INC-nnnn from the block's salt (salts are issued per incident as inc-nnnn-<random>)."""
    m = SALT_INCIDENT.match(canonical(blk).get("salt") or "")
    return m.group(1).upper() if m else None


def extra_prose(text: str) -> list[str]:
    """Lines of a disclosure POST that are not evidence (header, the three fields, JSON blocks, leading @mentions)."""
    rest, pos = "", 0
    for s, e, _c in fences(text):
        rest, pos = rest + text[pos:s], e
    rest += text[pos:]
    out = []
    for line in rest.splitlines():
        s = line.strip()
        if not s or MENTION_LINE.match(s) or FIELD.match(line):
            continue
        s = HEADER.sub("", s).strip()
        s = re.sub(r"^(?:@[\w.-]+[\s,:]*)+", "", s).strip()
        if s:
            out.append(s)
    return out
