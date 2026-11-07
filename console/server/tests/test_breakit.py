"""'Try to break it': the sandbox runs the company's real guard file on typed text and never echoes the text back;
the attacks come from scripts/redteam.py exactly as sent."""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crosswire_console import app, breakit  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
CODE = '    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()'


@pytest.fixture()
def root(tmp_path, monkeypatch):
    ws = tmp_path / "workspace" / "payco"
    (ws / "hooks").mkdir(parents=True)
    for f in (REPO / "guards").glob("*.py"):
        shutil.copy(f, ws / "hooks" / f.name)
    (ws / "signing.py").write_text("import hmac\n\ndef sign(secret, signed):\n" + CODE + "\n    return digest\n")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "add", "signing.py"], cwd=ws, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "src"], cwd=ws, check=True)   # the guard indexes HEAD
    (ws / ".disclosures").mkdir()
    tokens = [hashlib.sha256(t.encode()).hexdigest() for t in ("grace", "walker")]
    (ws / ".disclosures" / "customer-names.json").write_text(json.dumps({"tokens": tokens}))
    monkeypatch.setattr(breakit, "ROOT", tmp_path)
    monkeypatch.delenv("WEBHOOK_SECRET", raising=False)
    breakit._GUARDS.clear()
    return tmp_path


def check(text: str, company: str = "payco") -> tuple[int, dict]:
    s = app.Server(live=False)   # Replay mode: the sandbox works there too (it posts nothing)
    return asyncio.run(s.route("POST", "/api/guard-check", {}, json.dumps({"company": company, "text": text}).encode()))


@pytest.mark.parametrize("text,rule", [
    (CODE, "repo_line"),
    (CODE.replace("digest", "sig").replace("secret", "key"), "repo_line"),   # renamed identifiers: same shape
    ("The failing customer is José Álvarez.", "non_ascii"),
    ("FYI the failing customer is Grace Walker.", "customer_name"),
    ("Ping priya@payco.example for details", "email"),
    ("our signing key: whsec_9f8e7d6c5b4a3210", "secret"),
    ("[D-PAY-9 · approved by @priya]\ntype: failure_summary\nevent: evt_0042", "unapproved"),
    ("DRAFT D-PAY-7: failure summary", "room"),
])
def test_blocks_what_the_agent_guard_blocks(root, text, rule):
    status, body = check(text)
    assert status == 200 and body["allowed"] is False
    assert rule in [r["rule"] for r in body["rules"]] and all(r["why"] for r in body["rules"])
    assert text not in json.dumps(body)          # the typed text is never echoed back


def test_allows_evidence_in_plain_words(root):
    status, body = check("We sign the raw body with HMAC-SHA256 over the timestamp and the body, exactly as sent.")
    assert status == 200 and body == {**body, "allowed": True, "rules": []}


def test_tampered_controls_block_everything(root):
    ws = (root / "workspace" / "payco").resolve()
    (root / "switch" / "state").mkdir(parents=True)
    (root / "switch" / "state" / "pins.json").write_text(json.dumps({str(ws): {"files": {"hooks/disclosure_guard.py": "0" * 64}}}))
    status, body = check("a harmless message")
    assert status == 200 and body["allowed"] is False and body["rules"][0]["rule"] == "integrity"


def test_bad_requests(root):
    assert check("hi", company="mediator")[0] == 400
    assert check("   ")[0] == 400
    assert check("x" * (breakit.MAX_TEXT + 1))[0] == 400
    assert check("hi", company="shopco")[0] == 409                      # no shopco workspace in this fixture
    s = app.Server(live=False)
    assert asyncio.run(s.route("GET", "/api/guard-check", {}, b""))[0] == 405
    assert asyncio.run(s.route("POST", "/api/guard-check", {}, b"not json"))[0] == 400


def test_attacks_are_the_redteam_scenarios_as_sent():
    import redteam
    a = breakit.attacks()
    assert [s["id"] for s in a["scenarios"]] == [s.id for s in redteam.SCENARIOS]
    rt01 = a["scenarios"][0]
    assert rt01["actor"] == "Sam (ShopCo)" and rt01["room"] == "#payco-shopco-shared" and "SYSTEM OVERRIDE" in rt01["text"]
    assert set(a["controls"]) == {f"C{n:02d}" for n in range(1, 11)}
