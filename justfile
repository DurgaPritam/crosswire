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
    @if [ -f docker-compose.yml ]; then docker compose up -d --build; else echo "not built yet: Phase 2 creates docker-compose.yml"; fi

down:
    @if [ -f docker-compose.yml ]; then docker compose down; fi

# Send 60 webhooks (54 ASCII, 6 non-ASCII names)
simulate:
    @if [ -x scripts/simulate.sh ]; then ./scripts/simulate.sh; else echo "not built yet: Phase 2"; fi

# Expect exactly the 6 non-ASCII events to fail
verify-bug:
    @echo "not built yet: Phase 2"

# Apply reference-fixes in a temp copy; expect 60/60
verify-fixed:
    @echo "not built yet: Phase 2"

# Run every test suite
test:
    ./scripts/test-all.sh

# Run the notary protocol agent
notary:
    @echo "not built yet: Phase 5"

# Disclosure guard statistics per company
guard-stats company="payco":
    @echo "not built yet: Phase 6"

# Stop the Claude Code session in one agent dir (Console starts a fresh one on next mention)
restart-agent dir:
    d="{{dir}}"; ./scripts/restart-agent.sh "${d#dir=}"

# Health checklist for the whole system
doctor:
    @echo "not built yet: Phase 10"
