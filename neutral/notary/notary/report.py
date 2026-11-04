"""Deterministic replies. Facts only: never a cause, a guess or a recommendation."""

from __future__ import annotations

from wirecheck import compare

from .disclosures import FINGERPRINT_TYPE, Disclosure, DisclosureError

HELP = """**notary** (deterministic, no AI). Commands:
- `compare <D-PAY-n> <D-SHOP-n>`: compare PayCo's and ShopCo's approved fingerprint disclosures for the same event,
  byte by byte (lengths, salted hashes, escapes per JSON field). Both must use the incident salt.
- `help`: this list.
I report facts about bytes. The mediator interprets them."""

UNKNOWN = "I only understand `compare <D-PAY-n> <D-SHOP-n>` and `help`."


def _yn(value: bool | None) -> str:
    return "-" if value is None else ("yes" if value else "no")


def _n(value: int | None) -> str:
    return "-" if value is None else str(value)


def _signed(value: int | None) -> str:
    return "-" if value is None else f"{value:+d}"


def check_pair(pay: Disclosure, shop: Disclosure) -> None:
    for d in (pay, shop):
        expected = FINGERPRINT_TYPE[d.side]
        if d.type != expected:
            raise DisclosureError(f"{d.d_id} is a {d.type}, not a {expected}; I can only compare fingerprints")
    if pay.salt != shop.salt:
        raise DisclosureError(f"different salts: {pay.d_id} uses {pay.salt}, {shop.d_id} uses {shop.salt}. "
                              "Both fingerprints must use the incident salt")
    if pay.event != shop.event:
        raise DisclosureError(f"different events: {pay.d_id} is {pay.event}, {shop.d_id} is {shop.event}")


def comparison(pay: Disclosure, shop: Disclosure) -> str:
    check_pair(pay, shop)
    assert pay.fingerprint is not None and shop.fingerprint is not None
    r = compare(pay.fingerprint, shop.fingerprint)
    lines = [
        f"**Notary · {pay.d_id} vs {shop.d_id}** · event {pay.event} · salt {pay.salt}",
        "",
        "| path | PayCo bytes | ShopCo bytes | delta | match | escaped (PayCo/ShopCo) |",
        "|---|---:|---:|---:|:-:|:-:|",
    ]
    for row in r["rows"]:
        lines.append(f"| {row['path']} | {_n(row['len_a'])} | {_n(row['len_b'])} | {_signed(row['delta'])} | "
                     f"{_yn(row['hash_match'])} | {_yn(row['escaped_a'])}/{_yn(row['escaped_b'])} |")
    lines += ["", f"Whole body: {r['total_bytes_a']} vs {r['total_bytes_b']} bytes (delta {r['total_delta']:+d}), "
                  f"{'hashes match' if r['body_match'] else 'hashes differ'}."]
    first = r["first_difference"]
    if first is None:
        lines.append("No difference: every field has the same bytes.")
    else:
        row = next(x for x in r["rows"] if x["path"] == first)
        delta = "n/a (missing on one side)" if row["delta"] is None else f"{row['delta']:+d}"
        lines.append(f"First difference: {first}, delta {delta} bytes.")
    return "\n".join(lines)
