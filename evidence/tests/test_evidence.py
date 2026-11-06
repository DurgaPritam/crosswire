"""Evidence servers: tool behaviour on fixture databases, plus live checks after `just simulate`.

Unit tests build PayCo/ShopCo databases with the companies' own code paths (PayCo's
serializer; ShopCo's JSON.stringify equivalent) and call the tool functions directly.
Live tests (skipped unless both servers answer) call every tool over MCP streamable HTTP
and assert that no customer name from the simulation appears in any output.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evidence/payco-mcp"), str(ROOT / "evidence/shopco-mcp"), str(ROOT / "scripts"),
                str(ROOT / "companies/payco/api")]

import payco_evidence.tools as pt  # noqa: E402
import shopco_evidence.tools as st  # noqa: E402
import simulate  # noqa: E402
from payco.deliveries import DeliveryLog  # noqa: E402
from payco.events import build_payment_succeeded, serialize  # noqa: E402
from wirecheck import compare  # noqa: E402

SALT = "inc-0001-7f3a"
CUSTOMERS = simulate.customers()
NAMES = [c["name"] for c in CUSTOMERS]
NAME_PARTS = sorted({part for n in NAMES for part in n.split()} , key=len, reverse=True)


def assert_no_values(output: object) -> None:
    text = json.dumps(output, ensure_ascii=False)
    escaped = json.dumps(output)
    for part in NAME_PARTS:
        assert part not in text and part not in escaped, f"customer name part {part!r} leaked"
        assert json.dumps(part)[1:-1] not in escaped, f"escaped name part {part!r} leaked"


@pytest.fixture(scope="module")
def dbs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    d = tmp_path_factory.mktemp("evidence")
    payco_db, shopco_db = d / "deliveries.db", d / "jobs.db"
    log = DeliveryLog(payco_db)
    shop = sqlite3.connect(shopco_db)
    shop.executescript((ROOT / "companies/shopco/app/lib/db.js").read_text().split("const SCHEMA = `")[1].split("`;")[0])
    for n, c in enumerate(CUSTOMERS, 1):
        e = build_payment_succeeded(f"evt_{n:04d}", c["amount_cents"], c["currency"],
                                    {"id": c["id"], "name": c["name"], "country": c["country"]}, created=1762300800 + n)
        body = serialize(e)                                                     # what PayCo sent
        verified = json.dumps(e, separators=(",", ":"), ensure_ascii=False).encode()  # JSON.stringify(parsed)
        ok = body == verified
        log.record(e["id"], body, "t=1,v1=" + "0" * 64, 202 if ok else 401)
        shop.execute("INSERT INTO jobs (event_id, payload, status, processed_at) VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                     (e["id"], verified.decode(), "verified" if ok else "failed"))
        shop.execute("INSERT INTO verify_audit (event_id, bytes, ok) VALUES (?, ?, ?)", (e["id"], verified, int(ok)))
    shop.commit()
    shop.close()
    return payco_db, shopco_db


FAILED = ["evt_0007", "evt_0018", "evt_0029", "evt_0042", "evt_0051", "evt_0058"]


def test_payco_failed_deliveries(dbs: tuple[Path, Path]) -> None:
    out = pt.list_failed_deliveries(pt.connect_ro(str(dbs[0])))
    assert [r["event_id"] for r in out] == FAILED and {r["status"] for r in out} == {401}
    assert_no_values(out)


def test_payco_summary_is_the_non_ascii_clue(dbs: tuple[Path, Path]) -> None:
    out = pt.summarize_failures(pt.connect_ro(str(dbs[0])))
    assert out["deliveries"] == {"failed": 6, "ok": 54}
    assert out["by_non_ascii_field"] == {"data.customer.name non_ascii": {"failed": 6, "ok": 0},
                                         "no non_ascii fields": {"failed": 0, "ok": 54}}
    assert_no_values(out)


def test_shopco_failures_and_no_non_ascii_tool(dbs: tuple[Path, Path]) -> None:
    out = st.list_signature_failures(st.connect_ro(str(dbs[1])))
    assert [r["event_id"] for r in out] == FAILED
    assert not any("ascii" in name for name in dir(st)), "shopco must not offer a non-ASCII summary"
    assert_no_values(out)


def test_fingerprints_compare_to_name_plus_four(dbs: tuple[Path, Path]) -> None:
    fp_p = pt.get_delivery_fingerprint(pt.connect_ro(str(dbs[0])), "evt_0042", SALT)
    fp_s = st.get_verification_fingerprint(st.connect_ro(str(dbs[1])), "evt_0042", SALT)
    result = compare(fp_p, fp_s)
    assert result["differing_paths"] == ["data.customer.name"]
    row = next(r for r in result["rows"] if r["path"] == "data.customer.name")
    assert (row["delta"], row["escaped_a"], row["escaped_b"]) == (4, True, False)
    assert_no_values([fp_p, fp_s, result])


def test_every_event_fingerprint_is_value_free(dbs: tuple[Path, Path]) -> None:
    p, s = pt.connect_ro(str(dbs[0])), st.connect_ro(str(dbs[1]))
    for n in range(1, 61):
        eid = f"evt_{n:04d}"
        assert_no_values([pt.get_delivery_fingerprint(p, eid, SALT), st.get_verification_fingerprint(s, eid, SALT)])


def test_specs_are_value_free_and_shopco_spec_has_no_code() -> None:
    spec = pt.get_signing_spec(str(ROOT / "companies/payco/docs/webhooks.md"))
    assert "public_docs_excerpt" in spec and "HMAC" in spec["algorithm"]
    assert_no_values(spec)
    prose = st.get_verification_spec()["verifier"]
    for code_marker in ("require(", "function ", "=>", "JSON.stringify(", "createHmac", ";"):
        assert code_marker not in prose
    assert_no_values(st.get_verification_spec())


@pytest.mark.parametrize("bad_event,bad_salt", [("evt_0042'; --", SALT), ("evt_0042", ""), ("evt_0042", "a b"), ("../x", SALT)])
def test_bad_arguments_rejected(dbs: tuple[Path, Path], bad_event: str, bad_salt: str) -> None:
    with pytest.raises(ValueError):
        pt.get_delivery_fingerprint(pt.connect_ro(str(dbs[0])), bad_event, bad_salt)
    with pytest.raises(ValueError):
        st.get_verification_fingerprint(st.connect_ro(str(dbs[1])), bad_event, bad_salt)


def test_unknown_event_and_window(dbs: tuple[Path, Path]) -> None:
    with pytest.raises(LookupError):
        pt.get_delivery_fingerprint(pt.connect_ro(str(dbs[0])), "evt_9999", SALT)
    with pytest.raises(ValueError):
        pt.summarize_failures(pt.connect_ro(str(dbs[0])), since_minutes=0)


def test_read_only_connection(dbs: tuple[Path, Path]) -> None:
    with pytest.raises(sqlite3.OperationalError):
        pt.connect_ro(str(dbs[0])).execute("DELETE FROM deliveries")


# --------------------------------------------------------------------------- live (after just up && just simulate)


def _up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


live = pytest.mark.skipif(not (_up(7101) and _up(7102)), reason="evidence servers not running (just up)")


def _token(company: str) -> str | None:
    f = Path(__file__).resolve().parents[2] / "switch" / "state" / "evidence-tokens.json"
    return json.loads(f.read_text()).get(company) if f.exists() else None


async def _call_all(url: str, company: str) -> dict[str, object]:
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    results: dict[str, object] = {}
    tok = _token(company)
    client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {tok}"} if tok else {}, timeout=30)
    async with client, streamable_http_client(url, http_client=client) as (read, write, *_):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = [t.name for t in (await session.list_tools()).tools]
            results["_tools"] = names
            for name in names:
                args = {"event_id": "evt_0042", "salt": SALT} if "fingerprint" in name else {}
                r = await session.call_tool(name, args)
                assert not r.is_error, f"{name}: {r.content}"
                results[name] = r.structured_content if r.structured_content is not None else [c.model_dump() for c in r.content]
    return results


@live
def test_live_tools_never_return_names_and_pass_check() -> None:
    payco = asyncio.run(_call_all("http://localhost:7101/mcp", "payco"))
    shopco = asyncio.run(_call_all("http://localhost:7102/mcp", "shopco"))
    assert set(payco["_tools"]) == {"list_failed_deliveries", "get_delivery_fingerprint", "summarize_failures", "get_signing_spec"}
    assert set(shopco["_tools"]) == {"list_signature_failures", "get_verification_fingerprint", "get_verification_spec"}
    assert_no_values(payco)
    assert_no_values(shopco)

    def unwrap(x: object) -> dict:
        return x["result"] if isinstance(x, dict) and set(x) == {"result"} else x  # type: ignore[index,return-value]

    result = compare(unwrap(payco["get_delivery_fingerprint"]), unwrap(shopco["get_verification_fingerprint"]))
    assert result["differing_paths"] == ["data.customer.name"]
    row = next(r for r in result["rows"] if r["path"] == "data.customer.name")
    assert row["delta"] == 4
