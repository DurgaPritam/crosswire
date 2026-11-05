#!/usr/bin/env bash
# Full reset: stops services, removes Docker volumes and workspace/, then runs setup.
# Use before every rehearsal and before recording.
#
# Switch Console writes each agent's identity into its working directory (.switch/ and
# .claude/settings.local.json). Those are moved aside and put back untouched (never read),
# so the registered agents keep working after a reset.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.docker/bin"
if [ -f docker-compose.yml ] && command -v docker >/dev/null 2>&1; then
  docker compose down -v --remove-orphans || true
fi

keep="$(mktemp -d)"
trap 'rm -rf "$keep"' EXIT
for agent in payco shopco mediator; do
  for item in .switch .claude/settings.local.json; do
    if [ -e "workspace/$agent/$item" ]; then
      mkdir -p "$keep/$agent/$(dirname "$item")"
      mv "workspace/$agent/$item" "$keep/$agent/$item"
    fi
  done
done

rm -rf workspace
rm -f .tmp/last-simulate.json  # its event ids belonged to the wiped volumes
./scripts/setup.sh

for agent in payco shopco mediator; do
  [ -d "$keep/$agent" ] || continue
  (cd "$keep/$agent" && tar cf - .) | (cd "workspace/$agent" && tar xf -)
  echo "  restored Switch Console's agent identity files in workspace/$agent"
done
echo "reset done. Next: just up && just simulate"
