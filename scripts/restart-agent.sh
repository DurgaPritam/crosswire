#!/usr/bin/env bash
# Stop the Claude Code session(s) running in one agent working directory, so Switch
# Console starts a fresh session (with fresh settings/hooks) on the next mention.
#
#   scripts/restart-agent.sh workspace/payco          # stop it
#   scripts/restart-agent.sh --dry-run workspace/payco
#
# Matches processes named `claude` whose cwd is EXACTLY that directory (via lsof).
# Prints PID and cwd only: never the command line.
# Sends SIGTERM and confirms. Touches nothing else (not Console, not its session
# host, not Docker, not other Claude Code sessions, never this script's own ancestors).
set -euo pipefail

dry_run=0
escalate=0
while [ "${1:-}" = "--dry-run" ] || [ "${1:-}" = "--escalate" ]; do
  [ "$1" = "--dry-run" ] && dry_run=1
  [ "$1" = "--escalate" ] && escalate=1   # SIGINT, then SIGKILL, if a session ignores SIGTERM (same PIDs only)
  shift
done
if [ $# -ne 1 ]; then
  echo "usage: $0 [--dry-run] <agent-working-dir>" >&2
  exit 2
fi
if [ ! -d "$1" ]; then
  echo "error: $1 is not a directory" >&2
  exit 2
fi
target="$(cd "$1" && pwd -P)"

ancestors=" "
pid=$$
while [ "$pid" -gt 1 ] 2>/dev/null; do
  ancestors+="$pid "
  pid="$(ps -o ppid= -p "$pid" | tr -d ' ')"
  [ -n "$pid" ] || break
done

matches=()
while read -r pid comm; do
  [ "${comm##*/}" = "claude" ] || continue
  case "$ancestors" in *" $pid "*) continue ;; esac
  cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
  [ -n "$cwd" ] || continue
  cwd_real="$(cd "$cwd" 2>/dev/null && pwd -P || echo "$cwd")"
  [ "$cwd_real" = "$target" ] && matches+=("$pid")
done < <(ps -axo pid=,comm=)

if [ ${#matches[@]} -eq 0 ]; then
  echo "no Claude Code session running in $target (next mention starts a fresh one)"
  exit 0
fi

echo "Claude Code sessions in $target:"
for pid in "${matches[@]}"; do printf '  PID %s  cwd %s\n' "$pid" "$target"; done
if [ $dry_run -eq 1 ]; then echo "dry run: nothing stopped"; exit 0; fi

kill -TERM "${matches[@]}"
for _ in $(seq 1 20); do
  alive=()
  for pid in "${matches[@]}"; do kill -0 "$pid" 2>/dev/null && alive+=("$pid"); done
  [ ${#alive[@]} -eq 0 ] && { echo "stopped ${#matches[@]} session(s); Console starts a fresh one on the next mention"; exit 0; }
  sleep 0.5
done
if [ $escalate -eq 0 ]; then
  echo "error: still running after SIGTERM: ${alive[*]} (not escalating; check Console, or pass --escalate)" >&2
  exit 1
fi
for sig in INT KILL; do
  for pid in "${alive[@]}"; do
    [ "$(basename "$(ps -o comm= -p "$pid" 2>/dev/null)")" = "claude" ] && kill -"$sig" "$pid" 2>/dev/null
  done
  sleep 3
  still=()
  for pid in "${alive[@]}"; do kill -0 "$pid" 2>/dev/null && still+=("$pid"); done
  if [ ${#still[@]} -eq 0 ]; then
    echo "stopped ${#matches[@]} session(s) (escalated to SIG$sig for ${#alive[@]}); Console starts a fresh one on the next mention"
    exit 0
  fi
  alive=("${still[@]}")
done
echo "error: still running after SIGKILL: ${alive[*]}" >&2
exit 1
