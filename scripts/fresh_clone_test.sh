#!/usr/bin/env bash
# Fresh-clone test: clone this repo, follow only the README, and tear everything down again.
#
#   scripts/fresh_clone_test.sh [repo-or-url]     (default: this checkout)
#
# The clone gets its own COMPOSE_PROJECT_NAME, so it never shares containers or volumes with the main stack
# (Compose reads the variable ahead of docker-compose.yml's `name:`). The services use fixed host ports, so the
# main stack has to be down while this runs (`just down` there first); the script refuses to start otherwise.
set -uo pipefail
SRC="${1:-$(cd "$(dirname "$0")/.." && pwd -P)}"
export PATH="$PATH:$HOME/.docker/bin"
STAMP="$(date +%Y%m%d-%H%M%S)"
DIR="/tmp/crosswire-fresh-$STAMP"
export COMPOSE_PROJECT_NAME="crosswire-fresh-$STAMP"

for port in 7001 7002 7101 7102 7300 7400; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "port $port is in use: stop the main stack (just down) and any Console server first" >&2
    exit 2
  fi
done

git clone -q "$SRC" "$DIR" || exit 1
cd "$DIR" || exit 1
results=()
step() { # label, command...
  local label="$1"; shift
  if "$@" > "$DIR/.step.log" 2>&1; then results+=("PASS  $label"); else results+=("FAIL  $label (see $DIR/.step.log)"); tail -20 "$DIR/.step.log"; fi
}
step "just setup"         just setup
step "just up"            just up
step "just simulate"      just simulate
step "just verify-bug"    just verify-bug
step "just verify-fixed"  just verify-fixed
step "just test"          just test
just down >/dev/null 2>&1
docker compose down -v --remove-orphans >/dev/null 2>&1   # this project's volumes only

echo
echo "fresh clone of $SRC in $DIR (compose project $COMPOSE_PROJECT_NAME)"
printf '%s\n' "${results[@]}"
printf '%s\n' "${results[@]}" | grep -q '^FAIL' && exit 1
exit 0
