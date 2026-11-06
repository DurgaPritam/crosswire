"""Preflight's parser for the agents' INSTRUCTION-FILES line (context isolation check)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import preflight  # noqa: E402


@pytest.mark.parametrize("report,expected", [
    ("7) ok INSTRUCTION-FILES: CLAUDE.md (inside), AGENTS.md (inside)\n8) ok", [("CLAUDE.md", "inside"), ("AGENTS.md", "inside")]),
    ("INSTRUCTION-FILES: CLAUDE.md (inside) / 8) ok", [("CLAUDE.md", "inside")]),                 # run 15, payco-agent
    ("INSTRUCTION-FILES: `CLAUDE.md` (inside), CLAUDE.md (outside; given to me earlier in this conversation)",
     [("CLAUDE.md", "inside"), ("CLAUDE.md", "outside")]),                                         # stale context
    ("INSTRUCTION-FILES: none", []),
    ("INSTRUCTION-FILES: something I can't classify", [("something I can't classify", "?")]),
])
def test_parse(report, expected):
    assert preflight.instruction_files(report) == expected


def test_absent_line_is_none():
    assert preflight.instruction_files("7) ok\n8) ok") is None
