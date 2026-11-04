#!/usr/bin/env bash
# Creates workspace/: one independent git repo per company, plus the mediator dir.
# Runtime playbooks (AGENT.md) become CLAUDE.md and AGENTS.md inside the workspace.
# Idempotent: existing workspace repos are left alone (use scripts/reset.sh to rebuild),
# but each agent's .claude/settings.json is re-rendered on every run from the committed
# .claude/settings.template.json, because its deny rules need this machine's absolute paths.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd -P)"
WS="$ROOT/workspace"
export PATH="$PATH:$HOME/.docker/bin"

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
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

# Ignored inside each workspace repo: private state, generated machine-specific settings,
# Console's own settings.local.json, hook logs and the project-local temp dir.
WS_GITIGNORE='.disclosures/
node_modules/
__pycache__/
.switch/
.claude/settings.json
.claude/settings.local.json
hooks/*.log
.tmp/
.venv/
'

render_settings() { # name, other_company_name_or_empty
  local name="$1" other="$2" dst="$WS/$1" tpl="$WS/$1/.claude/settings.template.json"
  if [ ! -f "$tpl" ]; then
    echo "  (no .claude/settings.template.json in workspace/$name yet: Phase 6 adds it)"; return
  fi
  python3 "$ROOT/scripts/lib/render_settings.py" "$tpl" "$dst/.claude/settings.json" \
    "PROJECT_DIR=$dst" \
    "OTHER_COMPANY_DIR=$WS/${other:-__none__}" \
    "PAYCO_DIR=$WS/payco" "SHOPCO_DIR=$WS/shopco" "MEDIATOR_DIR=$WS/mediator" \
    "WORKSPACE_DIR=$WS" "REPO_DIR=$ROOT" "HOME=$HOME"
  echo "  rendered workspace/$name/.claude/settings.json"
}

make_repo() { # source_dir, target_name, baseline_message
  local src="$1" name="$2" msg="$3" dst="$WS/$2"
  if [ -d "$dst/.git" ]; then
    echo "workspace/$name exists, skipping (just reset to rebuild)"; return
  fi
  mkdir -p "$dst"
  # copy everything except the source-only README, AGENT.md and anything generated
  (cd "$src" && tar cf - --exclude=README.md --exclude=AGENT.md --exclude=node_modules \
      --exclude=__pycache__ --exclude=.claude/settings.json --exclude=.claude/settings.local.json \
      --exclude='*.log' --exclude=.tmp --exclude=.disclosures --exclude=.pytest_cache .) | (cd "$dst" && tar xf -)
  if [ -f "$src/AGENT.md" ]; then
    cp "$src/AGENT.md" "$dst/CLAUDE.md"
    cp "$src/AGENT.md" "$dst/AGENTS.md"
  fi
  mkdir -p "$dst/.disclosures"
  printf '%s' "$WS_GITIGNORE" > "$dst/.gitignore"
  ( cd "$dst" && git init -q && git add -A \
    && git -c user.name="Crosswire Setup" -c user.email="setup@crosswire.local" commit -q -m "$msg" )
  echo "created workspace/$name (git repo)"
}

make_repo "$ROOT/companies/payco"  payco  "PayCo baseline"
make_repo "$ROOT/companies/shopco" shopco "ShopCo baseline"

# mediator: plain directory (no repo needed), playbook only
if [ ! -d "$WS/mediator" ]; then
  mkdir -p "$WS/mediator"
  (cd "$ROOT/neutral/mediator" && tar cf - --exclude=README.md --exclude=AGENT.md \
      --exclude=.claude/settings.json --exclude=.claude/settings.local.json --exclude='*.log' .) | (cd "$WS/mediator" && tar xf -)
  cp "$ROOT/neutral/mediator/AGENT.md" "$WS/mediator/CLAUDE.md"
  echo "created workspace/mediator"
else
  echo "workspace/mediator exists, skipping"
fi

render_settings payco shopco
render_settings shopco payco
render_settings mediator ""

echo "setup done. Agent working dirs:"
echo "  payco-agent  -> $WS/payco"
echo "  shopco-agent -> $WS/shopco"
echo "  mediator     -> $WS/mediator"
