#!/usr/bin/env python3
"""Copy a red-team scorecard into docs/security/scorecards/ WITHOUT the evidence (agents' quoted posts).

Agents' replies can restate details that must never be published, so the committed copy keeps only ids, titles,
threats, verdicts and the reasons the classifier recorded. The full scorecard stays local in rehearsals/.

    scripts/publish_scorecard.py rehearsals/redteam-after-<ts>.json after
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "security" / "scorecards"
KEEP = ("id", "title", "threat", "verdict", "reasons")


def publish(src: Path, name: str) -> tuple[Path, Path]:
    d = json.loads(src.read_text(encoding="utf-8"))
    clean = {"label": d.get("label"), "ts": d.get("ts"), "counts": d.get("counts"), "control_counts": d.get("control_counts"),
             "results": [{k: r.get(k) for k in KEEP} for r in d.get("results", [])],
             "controls": [{k: r.get(k) for k in KEEP} for r in d.get("controls", [])]}
    OUT.mkdir(parents=True, exist_ok=True)
    j = OUT / f"{name}.json"
    j.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    md_src = src.with_suffix(".md")
    md = md_src.read_text(encoding="utf-8") if md_src.exists() else ""
    md = re.split(r"^## Evidence\b", md, flags=re.M)[0].rstrip() + "\n\n(Evidence, the agents' quoted posts, is kept locally only.)\n"
    m = OUT / f"{name}.md"
    m.write_text(md, encoding="utf-8")
    return j, m


if __name__ == "__main__":
    for p in publish(Path(sys.argv[1]), sys.argv[2]):
        print(p.relative_to(ROOT))
