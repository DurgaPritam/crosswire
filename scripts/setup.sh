#!/usr/bin/env bash
# Creates workspace/: one independent git repo per company, plus the mediator dir.
# Runtime playbooks (AGENT.md) become CLAUDE.md and AGENTS.md inside the workspace.
# Idempotent: existing workspace repos are left alone (use scripts/reset.sh to rebuild).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
WS="$ROOT/workspace"

if [ ! -f .env ]; then
  cp .env.example .env
  secret="$(python3 -c 'import secrets;print(secrets.token_hex(24))')"
  python3 - "$secret" << 'PY'
import sys, re
p = ".env"; s = open(p).read()
s = re.sub(r"^WEBHOOK_SECRET=.*$", "WEBHOOK_SECRET=" + sys.argv[1], s, flags=re.M)
open(p, "w").write(s)
PY
  echo "created .env with a random WEBHOOK_SECRET"
fi

mkdir -p "$WS"

make_repo() { # source_dir, target_name, baseline_message
  local src="$1" name="$2" msg="$3" dst="$WS/$2"
  if [ -d "$dst/.git" ]; then
    echo "workspace/$name exists, skipping (just reset to rebuild)"; return
  fi
  mkdir -p "$dst"
  # copy everything except the source-only README and AGENT.md
  (cd "$src" && tar cf - --exclude=README.md --exclude=AGENT.md --exclude=node_modules --exclude=__pycache__ .) | (cd "$dst" && tar xf -)
  if [ -f "$src/AGENT.md" ]; then
    cp "$src/AGENT.md" "$dst/CLAUDE.md"
    cp "$src/AGENT.md" "$dst/AGENTS.md"
  fi
  mkdir -p "$dst/.disclosures"
  printf ".disclosures/\nnode_modules/\n__pycache__/\n.switch/\n" > "$dst/.gitignore"
  ( cd "$dst" && git init -q && git add -A \
    && git -c user.name="Crosswire Setup" -c user.email="setup@crosswire.local" commit -q -m "$msg" )
  echo "created workspace/$name (git repo)"
}

make_repo "$ROOT/companies/payco"  payco  "PayCo baseline"
make_repo "$ROOT/companies/shopco" shopco "ShopCo baseline"

# mediator: plain directory (no repo needed), playbook only
if [ ! -d "$WS/mediator" ]; then
  mkdir -p "$WS/mediator"
  (cd "$ROOT/neutral/mediator" && tar cf - --exclude=README.md --exclude=AGENT.md .) | (cd "$WS/mediator" && tar xf -)
  cp "$ROOT/neutral/mediator/AGENT.md" "$WS/mediator/CLAUDE.md"
  echo "created workspace/mediator"
else
  echo "workspace/mediator exists, skipping"
fi

echo "setup done. Agent working dirs:"
echo "  payco-agent  -> $WS/payco"
echo "  shopco-agent -> $WS/shopco"
echo "  mediator     -> $WS/mediator"
