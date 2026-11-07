"""Export what the hosted Replay needs as plain files (`just console-static`): no server, no Switch.

    python -m crosswire_console.export_static <out_dir>

Writes <out_dir>/static/:
  config.json             replay-only config (switch_configured: false)
  replays/<name>.json     each committed recording in console/fixtures (already normalized: no payload values)
  security.json           the red-team scorecards and attacks (same as GET /api/security), plus `presets`: the real
                          disclosure guard's verdict on each sandbox example (console/web/src/security/presets.json),
                          run here against each company's workspace, so the hosted page can show real verdicts.
Needs `just setup` (the companies' workspaces) for the preset verdicts; without it they're left out and the page says
the sandbox needs the local console.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import breakit
from .app import FIXTURES, read_replay, security_summary
from .sources import ROOT

PRESETS = ROOT / "console" / "web" / "src" / "security" / "presets.json"


def preset_verdicts() -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for company, items in json.loads(PRESETS.read_text(encoding="utf-8")).items():
        for item in items:
            status, body = breakit.guard_check(company, item["text"])
            if status != 200:
                print(f"  presets: skipped ({body.get('error')})")
                return {}
            body.pop("secret_env", None)
            out.setdefault(company, {})[item["text"]] = body
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    static = Path(argv[0]) / "static"
    (static / "replays").mkdir(parents=True, exist_ok=True)
    names = sorted(f.name for f in FIXTURES.glob("*.events.jsonl"))
    for name in names:
        (static / "replays" / f"{name}.json").write_text(json.dumps(read_replay(name), separators=(",", ":")), encoding="utf-8")
    default = "demo-run.events.jsonl" if "demo-run.events.jsonl" in names else (names or [None])[-1]
    (static / "config.json").write_text(json.dumps({"switch_configured": False, "observer": "disabled", "replays": names,
                                                     "default_replay": default}), encoding="utf-8")
    presets = preset_verdicts()
    (static / "security.json").write_text(json.dumps({**security_summary(), "attacks": breakit.attacks(), "presets": presets}),
                                          encoding="utf-8")
    n = sum(len(v) for v in presets.values())
    print(f"exported {len(names)} recordings, the security page and {n} preset verdicts to {static}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
