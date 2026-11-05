"""Fix 5: more secret formats, ASCII customer names, and code matching that ignores spacing and renamed identifiers."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import disclosure_guard as g  # noqa: E402

SOURCE = "def verify(body: bytes, header: str, secret: str) -> bool:\n" \
         "    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()\n" \
         "    return hmac.compare_digest(expected, header.split('=', 1)[1])\n"


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "shopco"
    (r / "app").mkdir(parents=True)
    (r / "app" / "verify.py").write_text(SOURCE)
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b"]):
        subprocess.run(cmd, cwd=r, check=True)
    (r / ".disclosures").mkdir()
    toks = [hashlib.sha256(w.encode()).hexdigest() for w in ("alice", "smith", "grace", "young")]
    (r / ".disclosures" / "customer-names.json").write_text(json.dumps({"tokens": toks}))
    g.SHAPES.clear()
    return r


def rules(root: Path, text: str) -> list[str]:
    return g.check("mcp__switch__post_message", text, root)


@pytest.mark.parametrize("text", [
    "    expected = hmac.new(key.encode(), payload, hashlib.sha256).hexdigest()",       # two identifiers renamed
    "expected=hmac.new( secret.encode(),body,hashlib.sha256 ).hexdigest()",            # spacing changed
    "`return hmac.compare_digest(want, sig_header.split('=', 1)[1])`",                 # renamed, in markdown
])
def test_renamed_or_respaced_source_lines_are_caught(root, text):
    assert "repo_line" in rules(root, text)


@pytest.mark.parametrize("text", [
    "ShopCo computes the HMAC over the raw body and compares it in constant time.",
    '{"event_id": "evt_0007", "fields": [{"path": "data.customer.name", "len": 24}], "total_bytes": 187}',
    "Ran ./bin/test: 4 passed, 0 failed (2.1s).",
])
def test_ordinary_evidence_and_prose_pass(root, text):
    assert not {"repo_line", "customer_name", "secret"} & set(rules(root, text))


@pytest.mark.parametrize("text,hit", [
    ("FYI the failing customer is Alice Smith", True),
    ("failing customer: Smith, Alice", True),
    ("Grace Young's webhook failed", True),
    ("there is a grace period before retries; young accounts too", False),     # lower case words, not names
    ("Alice from support asked about it", False),                              # one name token alone
])
def test_customer_names(root, text, hit):
    assert ("customer_name" in rules(root, text)) is hit


@pytest.mark.parametrize("text", [
    "token: github_pat_11ABCDEFG0123456789_abcdefghijklmnop",
    "use sk_live_51HabcdEFGhijkLMN",
    "auth eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "WEBHOOK_SECRET=s3cr3t-value-123",
    '"api_key": "abcd1234efgh5678"',
    "postgres://app:hunter2pass@db.internal/payments",
])
def test_secret_formats(root, text):
    assert "secret" in rules(root, text)


@pytest.mark.parametrize("text", ["the webhook secret is rotated weekly", "WEBHOOK_SECRET=<redacted>",
                                  "salt: inc-0001-ab12cd34", "password: ********"])
def test_secret_mentions_without_values_pass(root, text):
    assert "secret" not in rules(root, text)
