#!/usr/bin/env python3
"""PreToolUse guard that keeps file and shell access inside the agent's project directory.

Canonical copy: crosswire/guards/path_guard.py (proven in spikes S1b/S1c). scripts/setup.sh copies it
into every agent workspace as hooks/path_guard.py. Edit it here, never in workspace/.

Second layer behind the permission deny rules in .claude/settings.json. Console runs
agents in auto mode, and spike S1 showed auto mode reads outside the working directory
with no prompt, so the working directory is not a boundary on its own.

- File tools (Read, Write, Edit, MultiEdit, NotebookEdit, Glob, Grep): every path
  argument is resolved against the hook input's cwd with realpath (symlinks and ../
  are followed) and must land inside the project directory.
- Bash: blocked if the command contains a ../ segment, a ~ path, $HOME/$TMPDIR, a bare
  `cd` (goes home), or any absolute path or existing relative path / glob match that
  resolves outside the project. Only a few system tool locations are allowed outside.
  /tmp is deliberately NOT allowed: a shared temp dir is a side channel between company
  agents. Use the project-local .tmp/ instead.
- Unparseable input blocks (fail closed). Exit 2 + stderr blocks; exit 0 allows.

Every decision goes to hooks/path.log: tool, ALLOW/BLOCK, reason. Never file contents
and never the full command text.

Bash is also refused for process inspection (ps, pgrep, pkill, lsof, top, launchctl, sysctl: one agent
must not inspect another's processes) and for network tools (curl, wget, nc, ssh, ...: no side
channel to the other company's ports). With --mediator, Bash may only run the incident-salt command.

Known gaps (why this is "Medium", and containers are "Hard"): paths built at runtime
(string concatenation, base64, variables other than HOME/TMPDIR), and programs that
open files on their own (a script file, $TMPDIR used implicitly by tempfile).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
LOG_PATH = HOOKS_DIR / "path.log"  # the project's hooks/ (the guard is installed there)

ALLOWED_OUTSIDE_PREFIXES = ("/usr", "/bin", "/sbin", "/opt/homebrew")
ALLOWED_OUTSIDE_EXACT = ("/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr")

FILE_TOOL_PATH_KEYS = {
    "Read": ("file_path",),
    "Write": ("file_path",),
    "Edit": ("file_path",),
    "MultiEdit": ("file_path",),
    "NotebookEdit": ("notebook_path",),
    "Glob": ("path",),
    "Grep": ("path",),
}

# Word boundaries in shell text: start, whitespace, quotes, and shell punctuation.
_B = r"(?:^|[\s'\"`=(<>|;&])"
DOTDOT_RE = re.compile(_B + r"(?:[^\s'\"`;|&<>()]*/)?\.\.(?:/|$|[\s'\"`;|&<>()])")
TILDE_RE = re.compile(_B + r"~")
ENV_RE = re.compile(r"\$\{?(HOME|TMPDIR)\b")
BARE_CD_RE = re.compile(r"(?:^|[;&|(]|&&|\|\|)\s*(?:cd|pushd)\s*(?:$|[;&|)])")
# Absolute paths. ':' is not a boundary so URLs (https://host/x) are not read as paths.
ABS_RE = re.compile(r"(?:^|[\s'\"`=(<>|;&])(/[^\s'\"`;|&<>()]*)")
GLOB_CHARS = set("*?[")
# A COMMAND word: first word, after | ; & && || ( or a newline, inside $( ) or ` `, or the first word of
# a shell -c string (sh -c 'ps aux'). Optionally behind wrappers/assignments and with a directory prefix
# (/bin/ps). Quotes are NOT a boundary otherwise, so `git commit -m "top fix"` is fine.
_CMD_POS = (r"(?:^|[;&|(`\n]|\$\(|\b(?:sh|bash|zsh|dash|ksh)\s+-[a-z]*c[a-z]*\s+['\"])\s*"
            r"(?:(?:sudo|env|command|builtin|exec|nohup|time|nice|xargs|timeout\s+\S+|[A-Za-z_][A-Za-z0-9_]*=\S*)\s+)*"
            r"(?:[^\s;&|()'\"`]*/)?")
PROCESS_TOOLS = ("ps", "pgrep", "pkill", "lsof", "top", "htop", "launchctl", "sysctl")
NETWORK_TOOLS = ("curl", "wget", "nc", "ncat", "netcat", "socat", "telnet", "ssh", "scp", "sftp", "rsync", "ftp")
PROCESS_RE = re.compile(_CMD_POS + r"(" + "|".join(PROCESS_TOOLS) + r")(?=$|[\s;&|)'\"`])")
NETWORK_RE = re.compile(_CMD_POS + r"(" + "|".join(NETWORK_TOOLS) + r")(?=$|[\s;&|)'\"`])")
# The only Bash the mediator may run: the incident-salt one-liner from its playbook.
MEDIATOR_SALT_RE = re.compile(
    r"""python3 -c (['\"])import secrets; ?print\(('|\")inc-[0-9]{4}-\2 ?\+ ?secrets\.token_hex\([1-9][0-9]?\)\)\1""")
MEDIATOR = "--mediator" in sys.argv[1:]

# An agent's own controls live in its project directory: they may be READ, never changed by the agent.
# (.disclosures/approvals/ stays writable with the Write tool until approvals come from the approver service.)
PROTECTED = ("hooks", ".claude", ".mcp.json", ".disclosures", ".switch", "CLAUDE.md", "AGENTS.md")
WRITABLE_EXCEPTIONS = (".disclosures/approvals/", ".disclosures/ledger.jsonl")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PROTECTED_RE = re.compile(r"(?:^|[\s'\"`=(<>|;&:])(?:\./)?(" + "|".join(re.escape(x) for x in PROTECTED) + r")(?=$|/|[\s'\"`;|&<>()])")
ATTR_TOOLS = ("chmod", "chown", "chgrp", "chflags", "chattr", "xattr", "setfacl", "ln")
ATTR_RE = re.compile(_CMD_POS + r"(" + "|".join(ATTR_TOOLS) + r")(?=$|[\s;&|)'\"`])")


def _arg(flag: str) -> str | None:
    args = sys.argv[1:]
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


PINS = _arg("--pins")   # switch/state/pins.json (outside every workspace), written by `just setup`


class Blocked(Exception):
    pass


def log(decision: str, tool: str, reason: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    reason = reason.replace("\n", " ").replace("\t", " ")[:300]
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\t{decision}\t{tool}\t{reason}\n")


def project_dir() -> str:
    configured = os.environ.get("CLAUDE_PROJECT_DIR")
    base = configured if configured else str(HOOKS_DIR.parent)
    return os.path.realpath(base)


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root + os.sep)


def allowed_outside(path: str) -> bool:
    if path in ALLOWED_OUTSIDE_EXACT:
        return True
    return any(path == p or path.startswith(p + "/") for p in ALLOWED_OUTSIDE_PREFIXES)


def resolve(raw: str, cwd: str) -> str:
    return os.path.realpath(os.path.join(cwd, os.path.expanduser(raw)))


def check_path(raw: str, cwd: str, root: str, what: str) -> None:
    resolved = resolve(raw, cwd)
    if not inside(resolved, root):
        raise Blocked(f"{what} {raw!r} resolves to {resolved}, outside the project {root}")


def glob_static_prefix(pattern: str) -> str:
    parts = []
    for part in pattern.split("/"):
        if any(c in GLOB_CHARS for c in part):
            break
        parts.append(part)
    prefix = "/".join(parts)
    return prefix if prefix else ("/" if pattern.startswith("/") else ".")


def check_file_tool(tool: str, tool_input: dict, cwd: str, root: str) -> None:
    for key in FILE_TOOL_PATH_KEYS[tool]:
        value = tool_input.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise Blocked(f"{key} is not a string")
        check_path(value, cwd, root, key)
    if tool == "Glob":
        pattern = tool_input.get("pattern")
        if not isinstance(pattern, str):
            raise Blocked("Glob pattern is missing or not a string")
        if ".." in pattern.split("/"):
            raise Blocked(f"Glob pattern {pattern!r} contains a .. segment")
        base = tool_input.get("path") or cwd
        check_path(glob_static_prefix(pattern), base if os.path.isabs(base) else os.path.join(cwd, base), root, "Glob pattern")
    # Grep's `pattern` is a regex, not a path; only its `path` is checked above.


def check_bash(command: str, cwd: str, root: str) -> None:
    if MEDIATOR:
        if not MEDIATOR_SALT_RE.fullmatch(command.strip()):
            raise Blocked("the mediator may only run the incident-salt command from its playbook")
        return
    attr = ATTR_RE.search(command)
    if attr:
        raise Blocked(f"{attr.group(1)} is not allowed: file permissions and links are not the agent's to change")
    prot = PROTECTED_RE.search(command)
    if prot:
        raise Blocked(f"{prot.group(1)} is protected: read it with the Read tool; it can't be used in Bash")
    proc = PROCESS_RE.search(command)
    if proc:
        raise Blocked(f"process inspection ({proc.group(1)}) is not allowed: agents must not inspect each other's processes")
    net = NETWORK_RE.search(command)
    if net:
        raise Blocked(f"network tool ({net.group(1)}) is not allowed: use your evidence tools")
    if DOTDOT_RE.search(command):
        raise Blocked("command contains a ../ path segment")
    if TILDE_RE.search(command):
        raise Blocked("command contains a ~ home path")
    env = ENV_RE.search(command)
    if env:
        raise Blocked(f"command references ${env.group(1)}")
    if BARE_CD_RE.search(command):
        raise Blocked("bare cd/pushd changes to the home directory")

    # Raw scan: catches absolute paths even inside quoted code (python -c "open('/x')").
    for match in ABS_RE.finditer(command):
        raw = match.group(1)
        resolved = os.path.realpath(raw)
        if not inside(resolved, root) and not allowed_outside(resolved):
            raise Blocked(f"absolute path {raw!r} is outside the project")

    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError as exc:
        raise Blocked(f"command could not be parsed ({exc})") from exc

    for token in tokens:
        for candidate in [token, *token.split("=")[1:]]:
            if not candidate or candidate.startswith("-") and "=" not in candidate:
                continue
            if any(c in GLOB_CHARS for c in candidate):
                for match in glob.glob(candidate, root_dir=cwd):
                    resolved = resolve(match, cwd)
                    if not inside(resolved, root) and not allowed_outside(resolved):
                        raise Blocked(f"glob {candidate!r} matches {resolved}, outside the project")
                continue
            if "/" in candidate or os.path.lexists(os.path.join(cwd, candidate)):
                resolved = resolve(candidate, cwd)
                if not inside(resolved, root) and not allowed_outside(resolved):
                    raise Blocked(f"path {candidate!r} resolves to {resolved}, outside the project")


def check_protected_write(tool_input: dict, cwd: str, root: str) -> None:
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    rel = os.path.relpath(resolve(raw, cwd), root)
    if rel.startswith(WRITABLE_EXCEPTIONS) and not os.path.islink(resolve(raw, cwd)):
        return
    if any(rel == p or rel.startswith(p + "/") for p in PROTECTED + ("bin",)):
        raise Blocked(f"{rel} is one of this agent's own controls: it can be read, not changed")


def check_integrity(root: str) -> None:
    """Fail closed if a pinned control file (guards, settings, MCP config, playbook) differs from `just setup`'s."""
    if not PINS:
        return
    try:
        pins = json.loads(Path(PINS).read_text(encoding="utf-8")).get(root)
    except (OSError, ValueError) as exc:
        raise Blocked(f"integrity pins unreadable ({exc.__class__.__name__}): run `just setup`") from exc
    if not pins:
        raise Blocked("no integrity pins for this project: run `just setup`")
    import hashlib
    for rel, digest in pins["files"].items():
        f = Path(root) / rel
        actual = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else "missing"
        if actual != digest:
            raise Blocked(f"integrity check failed: {rel} differs from the pinned copy; run `just setup`")


def decide(event: dict) -> tuple[str, str]:
    tool = event.get("tool_name")
    tool_input = event.get("tool_input")
    cwd = event.get("cwd")
    if not isinstance(tool, str) or not isinstance(tool_input, dict) or not isinstance(cwd, str):
        raise Blocked("hook input is missing tool_name, tool_input or cwd")
    root = project_dir()
    cwd_real = os.path.realpath(cwd)
    if not inside(cwd_real, root):
        raise Blocked(f"session cwd {cwd_real} is outside the project {root}")
    check_integrity(root)

    if tool in FILE_TOOL_PATH_KEYS:
        check_file_tool(tool, tool_input, cwd_real, root)
        if tool in WRITE_TOOLS:
            check_protected_write(tool_input, cwd_real, root)
    elif tool == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            raise Blocked("Bash command is missing or not a string")
        check_bash(command, cwd_real, root)
    else:
        return tool, "not a guarded tool"
    return tool, "inside project"


def main() -> int:
    tool = "?"
    try:
        event = json.loads(sys.stdin.read())
        if not isinstance(event, dict):
            raise Blocked("hook input is not a JSON object")
        tool = event.get("tool_name") if isinstance(event.get("tool_name"), str) else "?"
        tool, reason = decide(event)
    except Blocked as exc:
        log("BLOCK", tool, str(exc))
        print(f"path_guard: blocked {tool}: {exc}. Stay inside this project directory; "
              "use .tmp/ in the project for temporary files.", file=sys.stderr)
        return 2
    except Exception as exc:  # fail closed on anything unexpected, including bad JSON
        log("BLOCK", tool, f"guard error: {exc!r}")
        print(f"path_guard: blocked {tool} because the guard could not evaluate it ({exc!r})",
              file=sys.stderr)
        return 2
    log("ALLOW", tool, reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
