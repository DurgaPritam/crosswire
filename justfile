# Crosswire commands. `just doctor` checks what each level needs; `just --list` shows every recipe.
set dotenv-load := true
export PATH := env_var('PATH') + ":" + env_var('HOME') + "/.docker/bin"
# wirecheck straight from the source tree: macOS can flag the editable install's .pth file hidden
# (e.g. under an iCloud-synced Desktop), and Python then skips it and `import wirecheck` fails.
export PYTHONPATH := justfile_directory() + "/packages/wirecheck" + if env_var_or_default('PYTHONPATH', '') == '' { '' } else { ':' + env_var('PYTHONPATH') }

default:
    @just --list

# Check tools (git, docker, python, node, just, claude, ../switch)
check:
    ./scripts/check-prereqs.sh

# Create workspace/ (one git repo per company) and .env
setup:
    ./scripts/setup.sh

# Wipe services, volumes and workspace/, then setup again
reset:
    ./scripts/reset.sh

# Start all services (company APIs, evidence servers, approver)
up:
    @[ -d workspace/payco ] || ./scripts/setup.sh
    docker compose up -d --build --wait

down:
    @if [ -f docker-compose.yml ]; then docker compose down; fi

# Send 60 webhooks (54 ASCII, 6 non-ASCII names)
simulate:
    ./scripts/simulate.sh

# Expect exactly the 6 non-ASCII events to fail
verify-bug:
    @[ -f .tmp/last-simulate.json ] || ./scripts/simulate.sh
    python3 scripts/verify_bug.py --expect bug

# Apply reference-fixes in a temp copy; expect 60/60
verify-fixed:
    ./scripts/ensure-venv.sh
    ./scripts/verify-fixed.sh

# Run every test suite
test:
    ./scripts/test-all.sh

# Run the notary protocol agent on the host (`just switch-setup` registers it and runs it in Docker)
notary:
    ./scripts/ensure-venv.sh
    cd neutral/notary && ../../.venv/bin/python -m notary

# Rebuild and (re)start the notary container from the current code
notary-up:
    docker compose --profile notary up -d --build notary

# Check the hash-chained ledgers: guard logs, the approver's signed ledger, and that every allowed disclosure was signed
verify-ledger:
    .venv/bin/python scripts/verify_ledger.py

# Restart the approver so it re-pins the agents' controls (after setup re-renders them)
approver-restart:
    docker compose up -d --build approver && docker compose restart approver

# One-time Notary registration (NOTARY_REGISTRATION_TOKEN = a registration key minted by `host`)
notary-register *args:
    cd neutral/notary && ../../.venv/bin/python -m notary.register {{args}}

# Disclosure guard statistics per company
guard-stats company="payco":
    ./scripts/guard-stats.sh {{company}}

# Stop the Claude Code session in one agent dir (Console starts a fresh one on next mention)
restart-agent dir:
    d="{{dir}}"; ./scripts/restart-agent.sh "${d#dir=}"

# Incident Console, Live mode (observer + guard logs), http://127.0.0.1:7300 (builds the web app first)
console:
    ./scripts/ensure-venv.sh
    cd console/web && ([ -d node_modules ] || npm ci --silent) && npm run build --silent
    cd console/server && ../../.venv/bin/python -m crosswire_console

# Incident Console, Replay mode (plays console/fixtures/demo-run.events.jsonl, rehearsal run 7; no Switch needed; ?replay=<file> picks another)
console-replay:
    ./scripts/ensure-venv.sh
    cd console/web && ([ -d node_modules ] || npm ci --silent) && npm run build --silent
    cd console/server && ../../.venv/bin/python -m crosswire_console --replay

# Hosted Replay: a static build (no server, no Switch) in console/web/dist-static, e.g. `vercel deploy console/web/dist-static --prod`
console-static:
    ./scripts/ensure-venv.sh
    cd console/web && ([ -d node_modules ] || npm ci --silent) && npx tsc --noEmit && VITE_STATIC=1 npx vite build --outDir dist-static --emptyOutDir
    cd console/server && ../../.venv/bin/python -m crosswire_console.export_static ../web/dist-static

# Health checklist for the whole system
# Are the prerequisites in place? Level 0 replay · 1 bug + fix (Docker) · 2 live with Switch. Read-only.
doctor *levels:
    python3 scripts/doctor.py {{levels}}

# Level 2: from a running Switch Console to Crosswire's agents, rooms, roles, policies and claims
switch-setup *args:
    ./scripts/ensure-venv.sh
    .venv/bin/python scripts/switch_setup.py {{args}}
