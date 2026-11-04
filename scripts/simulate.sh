#!/usr/bin/env bash
# Send 60 webhooks via PayCo (54 ASCII, 6 non-ASCII names). See scripts/simulate.py.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/simulate.py "$@"
