"""wirecheck: privacy-preserving fingerprints of JSON payloads.

fingerprint(raw, salt, event_id) describes the exact bytes of a payload (sizes, byte
offsets, salted hashes, JSON field paths) without any field values. compare(a, b)
explains where two fingerprints of "the same" payload differ.

Hashes are HMAC-SHA256 keyed with the incident salt, so they compare across companies
within one incident and mean nothing outside it. They are not a secrecy guarantee for
low-entropy fields against someone who knows the salt (a country code can be guessed);
both companies in an incident already hold the same payment data.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from .scanner import Leaf, ScanError, scan

__all__ = ["fingerprint", "compare", "ScanError", "Leaf", "scan", "HASH_HEX_CHARS"]

HASH_HEX_CHARS = 32  # 128-bit salted digests: plenty to compare, short enough to post


def _h(salt: str, data: bytes) -> str:
    return hmac.new(salt.encode("utf-8"), data, hashlib.sha256).hexdigest()[:HASH_HEX_CHARS]


def fingerprint(raw: bytes, salt: str, event_id: str) -> dict[str, Any]:
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("fingerprint() takes the raw payload bytes")
    if not salt:
        raise ValueError("a non-empty incident salt is required")
    raw = bytes(raw)
    return {
        "event_id": event_id,
        "total_bytes": len(raw),
        "sha256": _h(salt, raw),
        "fields": [
            {
                "path": leaf.path,
                "offset": leaf.start,
                "length": leaf.end - leaf.start,
                "hash": _h(salt, raw[leaf.start:leaf.end]),
                "non_ascii": leaf.non_ascii,
                "escaped": leaf.escaped,
            }
            for leaf in scan(raw)
        ],
    }


def compare(fp_a: dict[str, Any], fp_b: dict[str, Any]) -> dict[str, Any]:
    """Compare two fingerprints of the same event. delta = len_a - len_b (a = provider)."""
    fields_a = {f["path"]: f for f in fp_a["fields"]}
    fields_b = {f["path"]: f for f in fp_b["fields"]}
    order = [f["path"] for f in fp_a["fields"]] + [f["path"] for f in fp_b["fields"] if f["path"] not in fields_a]
    rows = []
    for path in order:
        a, b = fields_a.get(path), fields_b.get(path)
        len_a = a["length"] if a else None
        len_b = b["length"] if b else None
        rows.append({
            "path": path,
            "len_a": len_a,
            "len_b": len_b,
            "delta": (len_a - len_b) if a and b else None,
            "hash_match": bool(a and b and a["hash"] == b["hash"]),
            "escaped_a": a["escaped"] if a else None,
            "escaped_b": b["escaped"] if b else None,
        })
    differing = [r["path"] for r in rows if not r["hash_match"]]
    return {
        "event_id_a": fp_a["event_id"],
        "event_id_b": fp_b["event_id"],
        "total_bytes_a": fp_a["total_bytes"],
        "total_bytes_b": fp_b["total_bytes"],
        "total_delta": fp_a["total_bytes"] - fp_b["total_bytes"],
        "body_match": fp_a["sha256"] == fp_b["sha256"],
        "rows": rows,
        "differing_paths": differing,
        "first_difference": differing[0] if differing else None,
    }
