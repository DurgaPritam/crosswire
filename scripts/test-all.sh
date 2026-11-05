#!/usr/bin/env bash
# `just test`: runs every component's tests. Each suite reports separately; exit 1 if any fail.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.docker/bin"
./scripts/ensure-venv.sh || exit 1
[ -f spikes/agent-a/.claude/settings.json ] || ./spikes/render-settings.sh >/dev/null   # gitignored (absolute paths)
PY=.venv/bin/python
failed=()
run() { # name, command...
  local name="$1"; shift
  printf '\n=== %s\n' "$name"
  if "$@"; then echo "--- $name: ok"; else echo "--- $name: FAILED"; failed+=("$name"); fi
}
suite_if() { # name, path-that-must-exist, command...
  local name="$1" path="$2"; shift 2
  if [ -e "$path" ]; then run "$name" "$@"; else printf '\n=== %s: not built yet\n' "$name"; fi
}

run      "scripts (render_settings)"  $PY -m pytest -q tests
run      "spike hooks (path_guard, block)" $PY spikes/agent-a/hooks/test_path_guard.py
run      "spike runner"                $PY spikes/test_run_spikes.py
suite_if "wirecheck"        packages/wirecheck/tests          $PY -m pytest -q packages/wirecheck/tests
suite_if "payco api"        companies/payco/api/tests         $PY -m pytest -q companies/payco/api/tests
[ -d companies/shopco/app/node_modules ] || (cd companies/shopco/app && echo "installing ShopCo test deps (npm ci, one time)" && npm ci --silent >/dev/null)
suite_if "shopco app"       companies/shopco/app/test         bash -c 'cd companies/shopco/app && npm test --silent'
suite_if "evidence servers" evidence/tests                    $PY -m pytest -q evidence/tests
suite_if "notary"           neutral/notary/tests              $PY -m pytest -q neutral/notary/tests
suite_if "guards (path, disclosure)" guards/tests                $PY -m pytest -q guards/tests
suite_if "console server (normalize)" console/server/tests     bash -c 'cd console/server && ../../.venv/bin/python -m pytest -q tests'
suite_if "console web (typecheck)" console/web/node_modules      bash -c 'cd console/web && npx tsc --noEmit -p .'

echo
if [ ${#failed[@]} -gt 0 ]; then echo "FAILED suites: ${failed[*]}"; exit 1; fi
echo "all suites passed"
