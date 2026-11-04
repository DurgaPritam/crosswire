from __future__ import annotations

import json
import random
import string

import pytest

from wirecheck import ScanError, compare, fingerprint, scan

SALT = "inc-0001-7f3a"


def event(name: str) -> dict:
    return {"id": "evt_0042", "type": "payment.succeeded", "created": 1762300800,
            "data": {"amount_cents": 4200, "currency": "EUR",
                     "customer": {"id": "cus_0042", "name": name, "country": "FR"}}}


def provider_bytes(e: dict) -> bytes:   # PayCo: json.dumps compact, ensure_ascii
    return json.dumps(e, separators=(",", ":")).encode()


def consumer_bytes(e: dict) -> bytes:   # ShopCo: JSON.stringify(parsed) == raw UTF-8
    return json.dumps(e, separators=(",", ":"), ensure_ascii=False).encode()


def test_offsets_point_at_raw_slices() -> None:
    raw = provider_bytes(event("José"))
    fp = fingerprint(raw, SALT, "evt_0042")
    assert fp["total_bytes"] == len(raw)
    by_path = {f["path"]: f for f in fp["fields"]}
    assert list(by_path) == ["id", "type", "created", "data.amount_cents", "data.currency",
                             "data.customer.id", "data.customer.name", "data.customer.country"]
    name = by_path["data.customer.name"]
    assert raw[name["offset"]:name["offset"] + name["length"]] == b'"Jos\\u00e9"'
    assert name["non_ascii"] and name["escaped"]
    amount = by_path["data.amount_cents"]
    assert raw[amount["offset"]:amount["offset"] + amount["length"]] == b"4200"


def test_ascii_payload_matches_everywhere() -> None:
    e = event("Jane Doe")
    result = compare(fingerprint(provider_bytes(e), SALT, "evt_1"), fingerprint(consumer_bytes(e), SALT, "evt_1"))
    assert result["body_match"] is True
    assert result["total_delta"] == 0
    assert result["first_difference"] is None
    assert all(r["hash_match"] and r["delta"] == 0 for r in result["rows"])


def test_jose_only_name_differs_by_four() -> None:
    e = event("José")
    result = compare(fingerprint(provider_bytes(e), SALT, "evt_0042"), fingerprint(consumer_bytes(e), SALT, "evt_0042"))
    assert result["body_match"] is False
    assert result["differing_paths"] == ["data.customer.name"]
    assert result["first_difference"] == "data.customer.name"
    row = next(r for r in result["rows"] if r["path"] == "data.customer.name")
    assert row["delta"] == 4 and row["escaped_a"] is True and row["escaped_b"] is False
    assert result["total_delta"] == 4
    country = next(r for r in result["rows"] if r["path"] == "data.customer.country")
    assert country["hash_match"] and country["delta"] == 0  # same bytes, just shifted


def test_four_bytes_per_accented_character() -> None:
    e = event("Renée Dubois é")
    result = compare(fingerprint(provider_bytes(e), SALT, "x"), fingerprint(consumer_bytes(e), SALT, "x"))
    assert result["total_delta"] == 4 * 2  # two é


def test_different_salts_never_match() -> None:
    raw = provider_bytes(event("Jane Doe"))
    assert compare(fingerprint(raw, "a", "x"), fingerprint(raw, "b", "x"))["body_match"] is False


def test_missing_paths_and_arrays() -> None:
    a = fingerprint(b'{"a":[1,"x",{"b":null}],"c":true}', SALT, "x")
    assert [f["path"] for f in a["fields"]] == ["a[0]", "a[1]", "a[2].b", "c"]
    b = fingerprint(b'{"a":[1,"x",{"b":null}]}', SALT, "x")
    r = compare(a, b)
    assert r["differing_paths"] == ["c"] and r["rows"][-1]["len_b"] is None


def test_whitespace_and_escapes_handled() -> None:
    raw = b' { "k" : "a\\"b\\\\u0041" , "n" : -1.5e3 } '
    fields = fingerprint(raw, SALT, "x")["fields"]
    assert [f["path"] for f in fields] == ["k", "n"]
    assert fields[0]["escaped"] is False  # \\\\u0041 is an escaped backslash, then "u0041"


@pytest.mark.parametrize("bad", [b"", b"{", b'{"a":}', b'{"a":1}x', b'"\\x"', b'{"a":"\x01"}'])
def test_invalid_json_raises(bad: bytes) -> None:
    with pytest.raises(ScanError):
        scan(bad)


def test_requires_bytes_and_salt() -> None:
    with pytest.raises(TypeError):
        fingerprint("{}", SALT, "x")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        fingerprint(b"{}", "", "x")


def _value(rng: random.Random) -> str:
    alphabet = string.ascii_letters + " -'" + "éøłüñçßÅ漢字"
    # at least one character outside [0-9a-f] so a value can't hide inside a hex digest by chance
    return rng.choice("ghijkGHIJKéø") + "".join(rng.choice(alphabet) for _ in range(rng.randint(3, 14)))


def test_property_no_output_contains_any_value() -> None:
    rng = random.Random(1234)
    for _ in range(400):
        values = [_value(rng) for _ in range(rng.randint(1, 6))]
        doc = {f"k{i}": v for i, v in enumerate(values)}
        doc["nested"] = {"list": values[:2], "n": rng.randint(10**6, 10**9)}
        ensure_ascii = rng.random() < 0.5
        raw = json.dumps(doc, separators=(",", ":"), ensure_ascii=ensure_ascii).encode()
        other = json.dumps(doc, separators=(",", ":"), ensure_ascii=not ensure_ascii).encode()
        fp_a, fp_b = fingerprint(raw, SALT, "evt_x"), fingerprint(other, SALT, "evt_x")
        outputs = json.dumps([fp_a, fp_b, compare(fp_a, fp_b)], ensure_ascii=False)
        escaped_outputs = json.dumps([fp_a, fp_b, compare(fp_a, fp_b)])
        for v in values + [str(doc["nested"]["n"])]:
            assert v not in outputs and v not in escaped_outputs, f"value leaked: {v!r}"
            assert json.dumps(v)[1:-1] not in escaped_outputs
