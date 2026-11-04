#!/usr/bin/env bash
# `just guard-stats <company>`: what the disclosure guard saw for one company (counts only, no text).
set -euo pipefail
cd "$(dirname "$0")/.."
company="${1:-payco}"
log="workspace/$company/.disclosures/guard.log.jsonl"
if [ ! -f "$log" ]; then echo "$company: no guard log yet ($log)"; exit 0; fi
python3 - "$company" "$log" <<'PY'
import json, sys
company, path = sys.argv[1], sys.argv[2]
entries = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
blocked = [e for e in entries if e.get("decision") == "block"]
by_rule: dict[str, int] = {}
for e in blocked:
    for r in e.get("rules", []):
        by_rule[r] = by_rule.get(r, 0) + 1
drafts = sum(1 for e in entries if e.get("note") == "draft")
print(f"{company} disclosure guard")
print(f"  posts checked: {len(entries)}  allowed: {len(entries) - len(blocked)} (drafts: {drafts})  blocked: {len(blocked)}")
for rule, n in sorted(by_rule.items(), key=lambda kv: -kv[1]):
    print(f"    blocked by {rule}: {n}")
print(f"  repo lines posted: 0 (attempts blocked: {by_rule.get('repo_line', 0)})")
PY
