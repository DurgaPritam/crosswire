#!/usr/bin/env python3
"""Spike S3: PreToolUse guard for Switch post tools.

Blocks mcp__switch__post_message / mcp__switch__send_targeted_message when the
body contains BLOCKME. Exit 2 + stderr blocks the call (Claude sees stderr);
exit 0 lets the normal permission flow continue. Unparseable input fails closed.

Every invocation appends one line to hooks/block.log so S3 can tell
"hook never ran" apart from "hook ran and allowed".
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

GUARDED_TOOLS = {"mcp__switch__post_message", "mcp__switch__send_targeted_message"}
TRIGGER = "BLOCKME"
LOG_PATH = Path(__file__).resolve().parent / "block.log"


def log(decision: str, tool: str, detail: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}\t{decision}\t{tool}\t{detail}\n")


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw)
        tool = event["tool_name"]
        tool_input = event.get("tool_input") or {}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log("BLOCK", "?", f"unparseable hook input: {exc!r}")
        print(f"spike guard: could not parse hook input ({exc!r}); blocking by default", file=sys.stderr)
        return 2

    if tool not in GUARDED_TOOLS:
        log("ALLOW", tool, "not a guarded tool")
        return 0

    body = tool_input.get("body")
    if isinstance(body, str) and TRIGGER in body:
        log("BLOCK", tool, f"body contains {TRIGGER}")
        print(
            f"spike guard: blocked {tool} because the message body contains {TRIGGER}. "
            "Do not retry or rephrase to get around this.",
            file=sys.stderr,
        )
        return 2

    log("ALLOW", tool, "body clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
