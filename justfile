# Crosswire commands. Recipes not built yet print which phase builds them.
set dotenv-load := true
export PATH := env_var('PATH') + ":" + env_var('HOME') + "/.docker/bin"

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

# Start all services (built in Phases 2, 4, 5)
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
    ./scripts/verify-fixed.sh

# Run every test suite
test:
    ./scripts/test-all.sh

# Run the notary protocol agent (register once first: just notary-register, after Phase 7 creates `host`)
notary:
    ./scripts/ensure-venv.sh
    cd neutral/notary && ../../.venv/bin/python -m notary

# Rebuild and (re)start the notary container from the current code
notary-up:
    docker compose --profile notary up -d --build notary

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

# Health checklist for the whole system
doctor:
    @echo "not built yet: Phase 10"
