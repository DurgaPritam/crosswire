"""disclosure_guard with --approver: a disclosure crosses only with the approver's signed record for exactly the
evidence the human approved, and nothing else in the post. A stub approver here signs with a test key."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import disclosure_canon as canon  # noqa: E402

ed = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ed25519")
ser = pytest.importorskip("cryptography.hazmat.primitives.serialization")
GUARD = Path(__file__).resolve().parents[1] / "disclosure_guard.py"

DRAFT_BLOCK = ('[D-PAY-3 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0007\nsalt: inc-0001-ab12cd34\n'
               '```json\n{"event_id": "evt_0007", "fields": [{"path": "data.customer.name", "len": 24}], "total_bytes": 187}\n```')
KEY = ed.Ed25519PrivateKey.generate()


def signed(record: dict, key=KEY) -> dict:
    return {**record, "sig": key.sign(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hex()}


@pytest.fixture()
def approver():
    state = {"records": {}}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path == "/pubkey":
                body, code = {"ed25519": KEY.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()}, 200
            elif self.path.startswith("/approval/"):
                rec = state["records"].get(self.path.rsplit("/", 1)[1])
                body, code = (rec, 200) if rec else ({"error": "none"}, 404)
            else:
                body, code = {}, 404
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{srv.server_address[1]}"
    yield state
    srv.shutdown()


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    r = tmp_path / "payco"
    (r / ".disclosures").mkdir(parents=True)
    (r / "api").mkdir()
    (r / "api" / "x.py").write_text("print('hi')\n")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b"]):
        subprocess.run(cmd, cwd=r, check=True)
    return r


def post(root: Path, url: str, body: str) -> subprocess.CompletedProcess[str]:
    payload = {"tool_name": "mcp__switch__post_message", "tool_input": {"body": body}, "cwd": str(root)}
    return subprocess.run([sys.executable, str(GUARD), "--approver", url], input=json.dumps(payload), capture_output=True,
                          text=True, env={"CLAUDE_PROJECT_DIR": str(root), "PATH": "/usr/bin:/bin"}, timeout=30)


def approve(state, status: str = "approved", block: str = DRAFT_BLOCK, key=KEY) -> None:
    state["records"]["D-PAY-3"] = signed({"v": 1, "d_id": "D-PAY-3", "status": status, "incident": "INC-0001",
                                          "sha256": canon.digest(block), "approver": "priya"}, key)


def test_approved_block_crosses_even_with_leading_mention_and_reformatted_json(root, approver):
    approve(approver)
    reformatted = DRAFT_BLOCK.replace('{"event_id": "evt_0007", ', '{\n  "event_id":"evt_0007",\n  ')
    r = post(root, approver["url"], "@incident-commander " + reformatted)
    assert r.returncode == 0, r.stderr


def test_no_record_denied_bad_signature_or_no_approver_are_unsigned(root, approver):
    assert "[unsigned]" in post(root, approver["url"], DRAFT_BLOCK).stderr
    approve(approver, status="denied")
    assert "[unsigned]" in post(root, approver["url"], DRAFT_BLOCK).stderr
    approve(approver, key=ed.Ed25519PrivateKey.generate())          # signed by someone else's key
    assert "[unsigned]" in post(root, approver["url"], DRAFT_BLOCK).stderr
    approve(approver)
    assert "[unsigned]" in post(root, "http://127.0.0.1:9", DRAFT_BLOCK).stderr   # approver down: fail closed


def test_changed_evidence_is_blocked(root, approver):
    approve(approver)
    r = post(root, approver["url"], DRAFT_BLOCK.replace('"len": 24', '"len": 16'))
    assert r.returncode == 2 and "[changed]" in r.stderr


def test_unapproved_prose_alongside_the_block_is_blocked(root, approver):
    approve(approver)
    r = post(root, approver["url"], DRAFT_BLOCK + "\nAlso, all 60 deliveries succeeded.")
    assert r.returncode == 2 and "[prose]" in r.stderr


def test_backticks_inside_json_strings_are_evidence_not_prose(root, approver):
    spec = ('[D-PAY-2 · approved by @priya]\ntype: signing_spec\nevent: n/a\nsalt: inc-0001-ab12cd34\n```json\n'
            + json.dumps({"docs_excerpt": "Sign like this:\n```python\nhmac.new(key, body, sha256)\n```\nthen hex.",
                          "header": "X-PayCo-Signature"}, indent=2) + "\n```")
    assert canon.extra_prose("@incident-commander " + spec) == []
    approver["records"]["D-PAY-2"] = signed({"v": 1, "d_id": "D-PAY-2", "status": "approved", "incident": "INC-0001",
                                             "sha256": canon.digest(spec), "approver": "priya"})
    assert post(root, approver["url"], "@incident-commander " + spec).returncode == 0
    assert "[prose]" in post(root, approver["url"], spec + "\nPlus a note.").stderr
