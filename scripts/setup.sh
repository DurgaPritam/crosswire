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
hooks/
.tmp/
.venv/
'

render_settings() { # name, other_company_name_or_empty
  # Always from the COMMITTED template (not the workspace's copy), so template changes reach existing workspaces.
  local name="$1" other="$2" dst="$WS/$1" src tpl
  case "$name" in mediator) src="$ROOT/neutral/mediator" ;; *) src="$ROOT/companies/$name" ;; esac
  tpl="$src/.claude/settings.template.json"
  if [ ! -f "$tpl" ]; then
    echo "  (no .claude/settings.template.json for $name yet: Phase 6 adds it)"; return
  fi
  mkdir -p "$dst/.claude"
  cp "$tpl" "$dst/.claude/settings.template.json"
  [ -f "$src/.mcp.json" ] && cp "$src/.mcp.json" "$dst/.mcp.json"
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

# Each agent's controls are made immutable (macOS user-immutable flag) after rendering; lift it to re-render.
unlock_controls() { [ -d "$WS" ] && command -v chflags >/dev/null && chflags -R nouchg "$WS" 2>/dev/null; return 0; }
unlock_controls

# Guards: one canonical copy in guards/, copied into every agent workspace on every run.
install_guards() { # name, guards...
  local name="$1"; shift
  mkdir -p "$WS/$name/hooks"
  for g in "$@"; do cp "$ROOT/guards/$g" "$WS/$name/hooks/$g"; done
}
install_guards payco path_guard.py disclosure_guard.py disclosure_canon.py ed25519_verify.py ledger_chain.py
install_guards shopco path_guard.py disclosure_guard.py disclosure_canon.py ed25519_verify.py ledger_chain.py
install_guards mediator path_guard.py

# Test environments for the agents' own test commands (gitignored inside each workspace).
if [ -d "$WS/payco/api" ] && [ ! -x "$WS/payco/.venv/bin/python" ]; then
  py="$(command -v python3.12 || command -v python3)"
  "$py" -m venv "$WS/payco/.venv" && "$WS/payco/.venv/bin/pip" install -q -r "$WS/payco/api/requirements.txt" pytest \
    && echo "  created workspace/payco/.venv (PayCo's test deps)"
fi
if [ -f "$WS/shopco/app/package-lock.json" ] && [ ! -d "$WS/shopco/app/node_modules" ] && command -v npm >/dev/null; then
  (cd "$WS/shopco/app" && npm ci --silent >/dev/null 2>&1) && echo "  installed workspace/shopco/app/node_modules (ShopCo's test deps)"
fi

# Room ids for guard rule g (written by Phase 7 automation into the gitignored switch/state/rooms.json).
if [ -f "$ROOT/switch/state/rooms.json" ]; then
  python3 - "$ROOT/switch/state/rooms.json" "$WS" <<'PY'
import json, sys
from pathlib import Path
rooms = json.loads(Path(sys.argv[1]).read_text()); ws = Path(sys.argv[2])
for company in ("payco", "shopco"):
    d = ws / company / ".disclosures"; d.mkdir(parents=True, exist_ok=True)
    (d / "rooms.json").write_text(json.dumps({"private": rooms[f"{company}-internal"], "shared": rooms["payco-shopco-shared"]}))
print("  wrote .disclosures/rooms.json for payco and shopco (guard rule g)")
PY
fi

# Customer name tokens for the guard's customer_name rule, as sha256 of each lower-cased ASCII name part (both
# companies serve the same simulated customers). The names themselves never land in a workspace.
python3 - "$ROOT" "$WS" <<'PY'
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts"))
from simulate import customers
tokens = sorted({hashlib.sha256(part.lower().encode()).hexdigest()
                 for c in customers() for part in c["name"].split() if part.isascii() and len(part) >= 3})
for company in ("payco", "shopco"):
    d = Path(sys.argv[2]) / company / ".disclosures"; d.mkdir(parents=True, exist_ok=True)
    (d / "customer-names.json").write_text(json.dumps({"tokens": tokens}))
print(f"  wrote .disclosures/customer-names.json for payco and shopco ({len(tokens)} hashed name tokens)")
PY

render_settings payco shopco
render_settings shopco payco
render_settings mediator ""

# Per-company evidence-server tokens (gap 9): made once, kept across resets in the gitignored switch/state/. Each agent's
# .mcp.json sends its own company's token; each evidence container gets its token from switch/state/<company>-evidence.env.
python3 - "$ROOT" "$WS" <<'PY'
import json, os, secrets, sys
from pathlib import Path
root, ws = Path(sys.argv[1]), Path(sys.argv[2])
state = root / "switch" / "state"; state.mkdir(parents=True, exist_ok=True)
f = state / "evidence-tokens.json"
tokens = json.loads(f.read_text()) if f.exists() else {}
for company in ("payco", "shopco"):
    tokens.setdefault(company, secrets.token_urlsafe(32))
old = os.umask(0o077)
try:
    f.write_text(json.dumps(tokens))
    for company, tok in tokens.items():
        (state / f"{company}-evidence.env").write_text(f"EVIDENCE_TOKEN={tok}\n")
finally:
    os.umask(old)
for company in ("payco", "shopco"):
    m = ws / company / ".mcp.json"
    if m.exists():
        cfg = json.loads(m.read_text())
        for srv in cfg.get("mcpServers", {}).values():
            srv["headers"] = {"Authorization": f"Bearer {tokens[company]}"}
        m.write_text(json.dumps(cfg, indent=2) + "\n")
print("  evidence tokens: each company's .mcp.json carries its own (switch/state/evidence-tokens.json)")
PY

# Pin every agent's controls (guards, settings, MCP config, playbook, room ids) and make them immutable. The guards
# check these pins on every call and fail closed on a mismatch; preflight checks them between runs.
python3 - "$ROOT" "$WS" <<'PY'
import hashlib, json, sys
from pathlib import Path
root, ws = Path(sys.argv[1]), Path(sys.argv[2])
CONTROLS = ("hooks/path_guard.py", "hooks/disclosure_guard.py", "hooks/disclosure_canon.py", "hooks/ed25519_verify.py", "hooks/ledger_chain.py", ".claude/settings.json", ".mcp.json", "CLAUDE.md", "AGENTS.md",
            ".disclosures/rooms.json", ".disclosures/customer-names.json", "bin/test", "bin/sandbox-check")
pins = {}
for agent in ("payco", "shopco", "mediator"):
    d = (ws / agent).resolve()
    files = {rel: hashlib.sha256((d / rel).read_bytes()).hexdigest() for rel in CONTROLS if (d / rel).is_file()}
    pins[str(d)] = {"files": files}
out = root / "switch" / "state" / "pins.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pins, indent=1))
print(f"  pinned {sum(len(v['files']) for v in pins.values())} control files -> switch/state/pins.json")
PY
if command -v chflags >/dev/null; then
  for agent in payco shopco mediator; do
    for rel in hooks/path_guard.py hooks/disclosure_guard.py hooks/disclosure_canon.py hooks/ed25519_verify.py hooks/ledger_chain.py .claude/settings.json .mcp.json CLAUDE.md AGENTS.md .disclosures/rooms.json .disclosures/customer-names.json bin/test bin/sandbox-check; do
      [ -f "$WS/$agent/$rel" ] && chflags uchg "$WS/$agent/$rel"
    done
  done
  echo "  made the control files immutable (chflags uchg)"
fi

echo "setup done. Agent working dirs:"
echo "  payco-agent  -> $WS/payco"
echo "  shopco-agent -> $WS/shopco"
echo "  mediator     -> $WS/mediator"
