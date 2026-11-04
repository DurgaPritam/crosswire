#!/usr/bin/env python3
"""Render an agent's .claude/settings.json from its committed settings.template.json.

    render_settings.py <template> <output> KEY=VALUE [KEY=VALUE ...]

Placeholders look like {{PROJECT_DIR}}. Every placeholder in the template must be given,
and every value must be an absolute path, so a typo can't silently produce a deny rule
that guards nothing. The output must be valid JSON. Used by scripts/setup.sh; the
rendered file is machine-specific and is never committed (workspace/ is gitignored, and
each workspace repo ignores .claude/settings.json too).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def render(template: str, values: dict[str, str]) -> str:
    wanted = set(PLACEHOLDER.findall(template))
    missing = sorted(wanted - values.keys())
    if missing:
        raise SystemExit(f"render_settings: no value for placeholder(s) {missing}")
    for key, value in values.items():
        if not value.startswith("/"):
            raise SystemExit(f"render_settings: {key}={value!r} is not an absolute path")
    out = PLACEHOLDER.sub(lambda m: values[m.group(1)], template)
    json.loads(out)  # must stay valid JSON
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    template, output, *pairs = argv
    values = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"render_settings: bad argument {pair!r} (want KEY=VALUE)")
        values[key] = value.rstrip("/") or "/"
    text = render(Path(template).read_text(encoding="utf-8"), values)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
