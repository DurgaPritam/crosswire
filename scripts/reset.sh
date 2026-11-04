#!/usr/bin/env bash
# Full reset: stops services, removes Docker volumes and workspace/, then runs setup.
# Use before every rehearsal and before recording.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.docker/bin"
if [ -f docker-compose.yml ] && command -v docker >/dev/null 2>&1; then
  docker compose down -v --remove-orphans || true
fi
rm -rf workspace
./scripts/setup.sh
echo "reset done. Next: just up && just simulate"
