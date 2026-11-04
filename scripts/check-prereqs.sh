#!/usr/bin/env bash
# Checks the tools Crosswire needs. Safe to run any time.
set -u
export PATH="$PATH:$HOME/.docker/bin"  # Docker Desktop installs its CLI here
ok=0
check() { # name, command, hint
  if command -v "$2" >/dev/null 2>&1; then
    printf "  [ok]   %-12s %s\n" "$1" "$("$2" --version 2>/dev/null | head -1)"
  else
    printf "  [MISS] %-12s %s\n" "$1" "$3"; ok=1
  fi
}
echo "Crosswire prerequisites:"
check git git "https://git-scm.com"
check docker docker "https://docs.docker.com/get-docker/"
check python3 python3 "Python 3.11+"
check node node "Node 20+"
check just just "https://github.com/casey/just"
check claude claude "Claude Code"
if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
  echo "  [WARN] docker is installed but not running"; ok=1
fi
if [ ! -d ../switch/docs/official ]; then
  echo "  [WARN] ../switch not found. Run: (cd .. && git clone --depth 1 https://github.com/sandbox-quantum/switch.git)"; ok=1
fi
echo "  [info] Switch Console: install from https://github.com/sandbox-quantum/switch/releases/latest"
exit $ok
