"""guards/disclosure_guard.py: one blocked fixture per rule, plus normal posts and approved disclosures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[1] / "disclosure_guard.py"
SOURCE_LINE = "    signed = f\"{t}.\".encode(\"ascii\") + body"

FP = {"event_id": "evt_0042", "total_bytes": 182, "sha256": "ab" * 16,
      "fields": [{"path": "data.customer.name", "offset": 140, "length": 19, "hash": "cd" * 16,
                  "non_ascii": True, "escaped": True}]}
DISCLOSURE = ("[D-PAY-1 · approved by @priya]\ntype: delivery_fingerprint\nevent: evt_0042\nsalt: inc-0001-7f3a9c2e\n"
              "```json\n" + json.dumps(FP, indent=1) + "\n```")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "payco"
    (root / "api").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "api" / "signing.py").write_text("def sign(body, secret, t):\n" + SOURCE_LINE + "\n    return signed\n")
    (root / "docs" / "webhooks.md").write_text("The signature is computed over the JSON payload, prefixed with the timestamp.\n")
    (root / "package-lock.json").write_text('{"lockfileVersion": 3, "requires": true, "packages": {}}\n')
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], cwd=root, check=True)
    (root / ".disclosures").mkdir()
    return root


def guard(root: Path, body: str | None = None, tool: str = "mcp__switch__post_message", tool_input: dict | None = None,
          env: dict | None = None) -> subprocess.CompletedProcess[str]:
    payload = {"hook_event_name": "PreToolUse", "cwd": str(root), "tool_name": tool,
               "tool_input": tool_input if tool_input is not None else {"body": body}}
    e = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "WEBHOOK_SECRET")}
    e["CLAUDE_PROJECT_DIR"] = str(root)
    e.update(env or {})
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload), capture_output=True, text=True, env=e, timeout=20)


def approve(root: Path, d_id: str, status: str = "approved") -> None:
    with (root / ".disclosures" / "ledger.jsonl").open("a") as fh:
        fh.write(json.dumps({"id": d_id, "ts": "2026-11-05T10:00:00Z", "type": "delivery_fingerprint",
                             "event": "evt_0042", "approved_by": "priya", "status": status}) + "\n")


def log_entries(root: Path) -> list[dict]:
    return [json.loads(l) for l in (root / ".disclosures" / "guard.log.jsonl").read_text().splitlines()]


# ---------------------------------------------------------------- allowed

@pytest.mark.parametrize("body", [
    "Failed deliveries in the last 24h: 6 (evt_0007, evt_0018, evt_0029, evt_0042, evt_0051, evt_0058).",
    "PayCo signs t + '.' + the exact body bytes with HMAC-SHA256; header PayCo-Signature: t=..,v1=..",
    "The signature is computed over the JSON payload, prefixed with the timestamp.",   # public docs (.md) quote
    "PayCo action item done: regression test added. Tests: 7 passed.",
])
def test_ordinary_posts_allowed(repo: Path, body: str) -> None:
    assert guard(repo, body).returncode == 0


def test_approved_disclosure_allowed(repo: Path) -> None:
    approve(repo, "D-PAY-1")
    r = guard(repo, DISCLOSURE)
    assert r.returncode == 0, r.stderr


def test_draft_allowed_before_approval(repo: Path) -> None:
    r = guard(repo, "DRAFT D-PAY-1: fingerprint of evt_0042 for the incident\n" + DISCLOSURE +
              "\nReply `approve D-PAY-1` or `deny D-PAY-1`.")
    assert r.returncode == 0, r.stderr
    assert log_entries(repo)[-1]["note"] == "draft"


def test_targeted_message_checked_too(repo: Path) -> None:
    r = guard(repo, tool="mcp__switch__send_targeted_message", tool_input={"target_roles": ["incident-commander"], "body": "ack"})
    assert r.returncode == 0


def test_other_tools_ignored(repo: Path) -> None:
    assert guard(repo, tool="Read", tool_input={"file_path": "x"}).returncode == 0


# ---------------------------------------------------------------- blocked, one per rule

def blocked(r: subprocess.CompletedProcess[str], rule: str) -> None:
    assert r.returncode == 2, f"expected block for {rule}: {r.stderr}"
    assert f"[{rule}]" in r.stderr and "disclosure_guard: blocked" in r.stderr


def test_a_repo_source_line(repo: Path) -> None:
    blocked(guard(repo, "Here is how we sign:\n" + SOURCE_LINE), "repo_line")
    blocked(guard(repo, "`signed = f\"{t}.\".encode(\"ascii\") + body`"), "repo_line")          # inside backticks
    blocked(guard(repo, "we do: signed   =  f\"{t}.\".encode(\"ascii\")   + body ok?"), "repo_line")  # whitespace + inline


def test_a_index_rebuilds_when_the_tree_changes(repo: Path) -> None:
    assert guard(repo, "new_helper_function_name_that_is_long = 1").returncode == 0
    (repo / "api" / "extra.py").write_text("new_helper_function_name_that_is_long = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    blocked(guard(repo, "new_helper_function_name_that_is_long = 1"), "repo_line")


def test_b_email(repo: Path) -> None:
    blocked(guard(repo, "Contact jose.alvarez@example.com about it"), "email")


def test_c_secrets(repo: Path) -> None:
    blocked(guard(repo, "secret is s3cr3t-value-123", env={"WEBHOOK_SECRET": "s3cr3t-value-123"}), "secret")
    blocked(guard(repo, "whsec_abcdef123456"), "secret")
    blocked(guard(repo, "-----BEGIN PRIVATE KEY-----"), "secret")


def test_d_non_ascii_letters(repo: Path) -> None:
    blocked(guard(repo, "The failing customer is José"), "non_ascii")
    blocked(guard(repo, "Łukasz"), "non_ascii")
    assert guard(repo, "delta +4 · ok → next").returncode == 0     # punctuation/symbols aren't letters


def test_e_unapproved_disclosure(repo: Path) -> None:
    blocked(guard(repo, DISCLOSURE), "unapproved")
    approve(repo, "D-PAY-1")
    approve(repo, "D-PAY-1", status="denied")                 # latest status wins
    blocked(guard(repo, DISCLOSURE), "unapproved")
    blocked(guard(repo, "type: failure_summary\nevent: n/a\n{}"), "unapproved")   # type line, no D-id at all


def test_e_one_approved_id_does_not_cover_another(repo: Path) -> None:
    approve(repo, "D-PAY-1")
    blocked(guard(repo, DISCLOSURE.replace("D-PAY-1", "D-PAY-2")), "unapproved")


def test_f_room_documents(repo: Path) -> None:
    blocked(guard(repo, tool="mcp__switch__create_room_document",
                  tool_input={"name": "INC-0001", "description": "x", "instructions": "", "content": "record"}), "room_doc")
    blocked(guard(repo, tool="mcp__switch__update_room_document", tool_input={"document_id": "d", "content": "x"}), "room_doc")


def test_unparseable_input_fails_closed(repo: Path) -> None:
    r = subprocess.run([sys.executable, str(GUARD)], input="not json", capture_output=True, text=True,
                       env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)})
    assert r.returncode == 2


def test_log_never_contains_the_text(repo: Path) -> None:
    guard(repo, "The failing customer is José at jose@example.com")
    guard(repo, "all good here, nothing sensitive at all")
    raw = (repo / ".disclosures" / "guard.log.jsonl").read_text()
    assert "Jos" not in raw and "example.com" not in raw and "nothing sensitive" not in raw
    entries = log_entries(repo)
    assert entries[0]["decision"] == "block" and set(entries[0]["rules"]) == {"email", "non_ascii"}
    assert entries[1]["decision"] == "allow" and entries[1]["length"] > 0


def test_guard_runs_without_git_repo(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert guard(plain, "hello there").returncode == 0
    blocked(guard(plain, "José"), "non_ascii")
