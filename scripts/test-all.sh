#!/usr/bin/env bash
# `just test`: runs every component's tests. Each suite reports separately; exit 1 if any fail.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$PATH:$HOME/.docker/bin"
if [ ! -x .venv/bin/python ]; then
  echo "creating .venv (python3.12 if available) from requirements-dev.txt"
  "$(command -v python3.12 || command -v python3)" -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt || exit 1
fi
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
suite_if "shopco app"       companies/shopco/app/test         bash -c 'cd companies/shopco/app && npm test --silent'
suite_if "evidence servers" evidence/tests                    $PY -m pytest -q evidence/tests
suite_if "notary"           neutral/notary/tests              $PY -m pytest -q neutral/notary/tests
suite_if "guards (path, disclosure)" guards/tests                $PY -m pytest -q guards/tests

echo
if [ ${#failed[@]} -gt 0 ]; then echo "FAILED suites: ${failed[*]}"; exit 1; fi
echo "all suites passed"
