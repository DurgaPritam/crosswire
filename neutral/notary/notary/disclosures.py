"""Parse approved disclosure messages posted by the company agents.

    [D-PAY-3 · approved by @priya]
    type: delivery_fingerprint
    event: evt_0042
    salt: inc-0001-7f3a
    ```json
    { ...wirecheck fingerprint... }
    ```
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

D_ID = re.compile(r"\bD-(PAY|SHOP)-(\d+)\b")
HEADER = re.compile(r"^\s*\[(D-(?:PAY|SHOP)-\d+)\s*[·|\-:]\s*approved by @([A-Za-z0-9._-]+)\]\s*$", re.M)
FIELD = re.compile(r"^\s*(type|event|salt)\s*:\s*(\S+)\s*$", re.M)
JSON_BLOCK = re.compile(r"```(?:json)?\s*\n(.*?)\n\s*```", re.S)

FINGERPRINT_TYPE = {"PAY": "delivery_fingerprint", "SHOP": "verification_fingerprint"}
FINGERPRINT_KEYS = {"event_id", "total_bytes", "sha256", "fields"}
FIELD_KEYS = {"path", "offset", "length", "hash", "non_ascii", "escaped"}


class DisclosureError(ValueError):
    """A disclosure exists but can't be used; the message says exactly why."""


@dataclass(frozen=True)
class Disclosure:
    d_id: str
    side: str            # "PAY" | "SHOP"
    approved_by: str
    type: str
    event: str
    salt: str
    fingerprint: dict[str, Any] | None
    message_id: str | None = None


def side_of(d_id: str) -> str:
    m = D_ID.fullmatch(d_id)
    if not m:
        raise DisclosureError(f"{d_id!r} is not a disclosure id (expected D-PAY-<n> or D-SHOP-<n>)")
    return m.group(1)


def find_in(body: str) -> list[str]:
    """D-ids of every disclosure header in a message body."""
    return [m.group(1) for m in HEADER.finditer(body or "")]


def parse(body: str, d_id: str, message_id: str | None = None) -> Disclosure:
    """Parse the disclosure `d_id` out of `body`. Raises DisclosureError with a precise reason."""
    headers = list(HEADER.finditer(body))
    start = next((m for m in headers if m.group(1) == d_id), None)
    if start is None:
        raise DisclosureError(f"{d_id}: no '[{d_id} · approved by @<owner>]' header")
    following = [m.start() for m in headers if m.start() > start.start()]
    section = body[start.end():following[0] if following else len(body)]

    fields = {k: v for k, v in FIELD.findall(section)}
    missing = [k for k in ("type", "event", "salt") if k not in fields]
    if missing:
        raise DisclosureError(f"{d_id}: missing {', '.join(missing)} line(s)")

    side = side_of(d_id)
    fp: dict[str, Any] | None = None
    if fields["type"].endswith("_fingerprint"):
        block = JSON_BLOCK.search(section)
        if not block:
            raise DisclosureError(f"{d_id}: no ```json fingerprint block")
        try:
            fp = json.loads(block.group(1))
        except json.JSONDecodeError as exc:
            raise DisclosureError(f"{d_id}: fingerprint JSON is malformed ({exc.msg} at line {exc.lineno})") from exc
        _validate_fingerprint(d_id, fp)
        if fp["event_id"] != fields["event"]:
            raise DisclosureError(f"{d_id}: header says event {fields['event']} but the fingerprint is for {fp['event_id']}")
    return Disclosure(d_id, side, start.group(2), fields["type"], fields["event"], fields["salt"], fp, message_id)


def _validate_fingerprint(d_id: str, fp: Any) -> None:
    if not isinstance(fp, dict) or not FINGERPRINT_KEYS <= fp.keys():
        raise DisclosureError(f"{d_id}: fingerprint must have {sorted(FINGERPRINT_KEYS)}")
    if not isinstance(fp["fields"], list) or not all(isinstance(f, dict) and FIELD_KEYS <= f.keys() for f in fp["fields"]):
        raise DisclosureError(f"{d_id}: every fingerprint field needs {sorted(FIELD_KEYS)}")
    if not isinstance(fp["total_bytes"], int):
        raise DisclosureError(f"{d_id}: total_bytes must be an integer")
