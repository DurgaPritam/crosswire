"""Tests for the canonical guards/path_guard.py (ported from the spike suite, plus process/network/mediator).

Each test builds a throwaway copy of the spike layout in a temp dir:

    <tmp>/agent-a/            project (CLAUDE_PROJECT_DIR), with hooks/ copied in
    <tmp>/agent-a/link-to-b   symlink -> ../agent-b/secret-b.txt
    <tmp>/agent-b/secret-b.txt

so the real hooks/path.log and the repo are never touched.

    .venv/bin/python -m pytest guards/tests
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1]  # guards/
CANARY = "canary-c42e08"


class Layout:
    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pathguard-")).resolve()
        self.a = self.tmp / "agent-a"
        self.b = self.tmp / "agent-b"
        (self.a / "hooks").mkdir(parents=True)
        self.b.mkdir()
        shutil.copy(HOOKS / "path_guard.py", self.a / "hooks" / "path_guard.py")
        (self.a / "secret-a.txt").write_text("canary-7f3a91\n")
        (self.a / "notes.txt").write_text("inside\n")
        (self.a / ".tmp").mkdir()
        (self.b / "secret-b.txt").write_text(CANARY + "\n")
        os.symlink("../agent-b/secret-b.txt", self.a / "link-to-b")
        self.log = self.a / "hooks" / "path.log"

    def run(self, event: dict | str, script: str = "path_guard.py", cwd: Path | None = None,
            args: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
        if isinstance(event, dict):
            event = {"cwd": str(cwd or self.a), "hook_event_name": "PreToolUse", **event}
            payload = json.dumps(event)
        else:
            payload = event
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        env["CLAUDE_PROJECT_DIR"] = str(self.a)
        return subprocess.run([sys.executable, str(self.a / "hooks" / script), *args], input=payload,
                              capture_output=True, text=True, env=env, timeout=20)

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp)


class PathGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.l = Layout()

    def tearDown(self) -> None:
        self.l.cleanup()

    # helpers
    def allowed(self, tool: str, tool_input: dict, **kw) -> None:
        r = self.l.run({"tool_name": tool, "tool_input": tool_input}, **kw)
        self.assertEqual(r.returncode, 0, f"expected ALLOW for {tool} {tool_input}: {r.stderr}")

    def blocked(self, tool: str, tool_input: dict, **kw) -> None:
        r = self.l.run({"tool_name": tool, "tool_input": tool_input}, **kw)
        self.assertEqual(r.returncode, 2, f"expected BLOCK for {tool} {tool_input}")
        self.assertIn("path_guard: blocked", r.stderr)
        self.assertNotIn(CANARY, r.stderr)

    def bash_allowed(self, command: str) -> None:
        self.allowed("Bash", {"command": command})

    def bash_blocked(self, command: str) -> None:
        self.blocked("Bash", {"command": command})

    # file tools: allowed
    def test_read_inside_relative_and_absolute(self) -> None:
        self.allowed("Read", {"file_path": "secret-a.txt"})
        self.allowed("Read", {"file_path": str(self.l.a / "notes.txt")})

    def test_write_edit_inside(self) -> None:
        self.allowed("Write", {"file_path": str(self.l.a / ".tmp" / "x.txt"), "content": "x"})
        self.allowed("Edit", {"file_path": str(self.l.a / "notes.txt"), "old_string": "a", "new_string": "b"})

    def test_glob_and_grep_inside(self) -> None:
        self.allowed("Glob", {"pattern": "**/*.py"})
        self.allowed("Grep", {"pattern": r"\.\./weird regex", "path": "."})
        self.allowed("Grep", {"pattern": "x"})

    # file tools: blocked
    def test_read_parent_relative(self) -> None:
        self.blocked("Read", {"file_path": "../agent-b/secret-b.txt"})

    def test_read_absolute_other_agent(self) -> None:
        self.blocked("Read", {"file_path": str(self.l.b / "secret-b.txt")})

    def test_read_symlink_to_other_agent(self) -> None:
        self.blocked("Read", {"file_path": str(self.l.a / "link-to-b")})
        self.blocked("Read", {"file_path": "link-to-b"})

    def test_read_home(self) -> None:
        self.blocked("Read", {"file_path": "~/.ssh/config"})

    def test_write_edit_notebook_outside(self) -> None:
        self.blocked("Write", {"file_path": str(self.l.b / "planted.txt"), "content": "x"})
        self.blocked("Edit", {"file_path": "../agent-b/secret-b.txt", "old_string": "a", "new_string": "b"})
        self.blocked("MultiEdit", {"file_path": "../agent-b/secret-b.txt", "edits": []})
        self.blocked("NotebookEdit", {"notebook_path": str(self.l.b / "n.ipynb"), "new_source": ""})

    def test_glob_grep_outside(self) -> None:
        self.blocked("Glob", {"pattern": "../agent-b/*"})
        self.blocked("Glob", {"pattern": "*", "path": str(self.l.b)})
        self.blocked("Glob", {"pattern": str(self.l.b) + "/*.txt"})
        self.blocked("Grep", {"pattern": "canary", "path": ".."})

    def test_tmp_is_outside(self) -> None:
        self.blocked("Read", {"file_path": "/tmp/x"})
        self.blocked("Write", {"file_path": "/tmp/x", "content": "x"})

    # Bash: allowed
    def test_bash_inside(self) -> None:
        self.bash_allowed("ls -la")
        self.bash_allowed("cat secret-a.txt notes.txt")
        self.bash_allowed("mkdir -p .tmp && cp notes.txt .tmp/")
        self.bash_allowed("python3 hooks/block.py < notes.txt 2>/dev/null")
        self.bash_allowed("/usr/bin/env python3 --version")
        self.bash_allowed("git log --oneline HEAD~1..HEAD")
        self.bash_allowed("echo see https://example.com/health")  # a URL is not a path
        self.bash_allowed("cat *.txt")
        self.bash_allowed(f"cat {self.l.a}/notes.txt")

    # Bash: blocked
    def test_bash_cat_parent(self) -> None:
        self.bash_blocked("cat ../agent-b/secret-b.txt")

    def test_bash_cat_absolute_and_full_binary_path(self) -> None:
        self.bash_blocked(f"cat {self.l.b}/secret-b.txt")
        self.bash_blocked(f"/bin/cat {self.l.b}/secret-b.txt")

    def test_bash_symlink_and_glob_through_symlink(self) -> None:
        self.bash_blocked("cat link-to-b")
        self.bash_blocked("cat link*")

    def test_bash_home_forms(self) -> None:
        self.bash_blocked("cat ~/.ssh/config")
        self.bash_blocked("cat $HOME/.ssh/config")
        self.bash_blocked("cat ${HOME}/.ssh/config")
        self.bash_blocked("cd && ls")
        self.bash_blocked("cd")

    def test_bash_tmp(self) -> None:
        self.bash_blocked("cat /tmp/x")
        self.bash_blocked("cp notes.txt /tmp/")
        self.bash_blocked("echo hi > /tmp/x")
        self.bash_blocked("ls $TMPDIR")

    def test_bash_paths_hidden_in_code_or_compound(self) -> None:
        self.bash_blocked(f"python3 -c \"print(open('{self.l.b}/secret-b.txt').read())\"")
        self.bash_blocked("ls && cd .. && cat agent-b/secret-b.txt")
        self.bash_blocked("sh -c 'cat ../agent-b/secret-b.txt'")
        self.bash_blocked("ls /")

    def test_bash_unparseable(self) -> None:
        self.bash_blocked("cat 'unterminated")

    # input handling
    def test_bad_input_fails_closed(self) -> None:
        self.assertEqual(self.l.run("not json").returncode, 2)
        self.assertEqual(self.l.run("[]").returncode, 2)
        self.assertEqual(self.l.run({"tool_name": "Bash", "tool_input": {}}).returncode, 2)
        self.assertEqual(self.l.run(json.dumps({"tool_name": "Read", "tool_input": {"file_path": "x"}})).returncode, 2)

    def test_cwd_outside_project_blocks(self) -> None:
        self.blocked("Read", {"file_path": "secret-b.txt"}, cwd=self.l.b)

    def test_unguarded_tool_allowed(self) -> None:
        self.allowed("WebSearch", {"query": "x"})

    def test_log_records_decisions_without_contents(self) -> None:
        self.l.run({"tool_name": "Read", "tool_input": {"file_path": "../agent-b/secret-b.txt"}})
        self.l.run({"tool_name": "Bash", "tool_input": {"command": "cat link-to-b"}})
        self.l.run({"tool_name": "Read", "tool_input": {"file_path": "notes.txt"}})
        lines = self.l.log.read_text().splitlines()
        self.assertEqual([ln.split("\t")[1:3] for ln in lines],
                         [["BLOCK", "Read"], ["BLOCK", "Bash"], ["ALLOW", "Read"]])
        self.assertNotIn(CANARY, self.l.log.read_text())


class ProcessNetworkAndMediator(unittest.TestCase):
    def setUp(self) -> None:
        self.l = Layout()

    def tearDown(self) -> None:
        self.l.cleanup()

    def code(self, command: str, *args: str) -> int:
        return self.l.run({"tool_name": "Bash", "tool_input": {"command": command}}, args=args).returncode

    def test_process_inspection_blocked(self) -> None:
        for cmd in ("ps aux", "ps", "/bin/ps -ef", "pgrep claude", "pkill node", "lsof -p 1", "top -l 1",
                    "launchctl list", "sysctl kern.procargs2", "ls && ps aux", "sh -c 'ps aux'", "echo $(ps)",
                    "sudo ps aux", "env X=1 ps", "X=1 ps"):
            self.assertEqual(self.code(cmd), 2, cmd)

    def test_network_tools_blocked(self) -> None:
        for cmd in ("curl http://localhost:7102/mcp", "wget x", "nc localhost 7102", "ssh host", "scp a b",
                    "/usr/bin/curl -s https://example.com", "bash -c 'curl x'"):
            self.assertEqual(self.code(cmd), 2, cmd)

    def test_ordinary_commands_still_allowed(self) -> None:
        for cmd in ("git status", "git log --oneline", "npm test", "ls -la", "python3 -m pytest -q",
                    "grep -rn psycopg notes.txt", "cat notes.txt | wc -l"):
            self.assertEqual(self.code(cmd), 0, cmd)

    def test_mediator_may_only_run_the_salt_command(self) -> None:
        salt = "python3 -c \"import secrets;print('inc-0001-'+secrets.token_hex(4))\""
        self.assertEqual(self.code(salt, "--mediator"), 0)
        self.assertEqual(self.code("python3 -c 'import secrets;print(\"inc-0042-\" + secrets.token_hex(4))'", "--mediator"), 0)
        for cmd in ("ls", "git status", "python3 -c \"import os;print(os.listdir('/'))\"",
                    salt + " && cat notes.txt", "python3 x.py"):
            self.assertEqual(self.code(cmd, "--mediator"), 2, cmd)
        r = self.l.run({"tool_name": "Read", "tool_input": {"file_path": "../agent-b/secret-b.txt"}}, args=("--mediator",))
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
