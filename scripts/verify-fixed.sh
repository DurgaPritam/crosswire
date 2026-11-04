#!/usr/bin/env bash
# `just verify-fixed`: apply reference-fixes/*.patch to a TEMPORARY copy of the company
# sources, run them as a separate compose project on other ports, simulate 60 events and
# expect 60/60. Never touches workspace/ or the main `crosswire` compose project.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd -P)"
export PATH="$PATH:$HOME/.docker/bin"
set -a; [ -f .env ] && . ./.env; set +a
: "${WEBHOOK_SECRET:?WEBHOOK_SECRET missing: run just setup}"

PROJECT=crosswire-fixed
export PAYCO_API_PORT=17001 SHOPCO_APP_PORT=17002
mkdir -p .tmp
TMP="$(mktemp -d "$ROOT/.tmp/verify-fixed.XXXXXX")"
cleanup() {
  docker compose -p "$PROJECT" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

for c in payco shopco; do
  mkdir -p "$TMP/$c"
  tar cf - --exclude=node_modules --exclude=__pycache__ --exclude=.pytest_cache -C "companies/$c" . | tar xf - -C "$TMP/$c"
done
apply_patch() { # company, patch
  # Own repo, so git resolves the patch paths here and not against crosswire's root.
  (cd "$TMP/$1" && git init -q && git apply --verbose "$ROOT/reference-fixes/$2" 2>&1 | tee "$TMP/$1.apply.log")
  if grep -q '^Skipped patch' "$TMP/$1.apply.log"; then echo "error: $2 did not apply cleanly" >&2; exit 1; fi
}
apply_patch payco payco-regression-test.patch
apply_patch shopco shopco-raw-body.patch

echo "--- patched unit tests"
.venv/bin/python -m pytest -q "$TMP/payco/api/tests" | tail -1
(cd "$TMP/shopco/app" && ln -s "$ROOT/companies/shopco/app/node_modules" node_modules && npm test --silent 2>&1 | grep -E '^ℹ (pass|fail)'; rm node_modules)

echo "--- starting patched services ($PROJECT on :$PAYCO_API_PORT/:$SHOPCO_APP_PORT)"
PAYCO_SRC="$TMP/payco" SHOPCO_SRC="$TMP/shopco" \
  docker compose -p "$PROJECT" up -d --build --wait payco-api shopco-app shopco-worker >/dev/null
python3 scripts/simulate.py --url "http://localhost:$PAYCO_API_PORT" --out "$TMP/sim.json"
python3 scripts/verify_bug.py --expect fixed --project "$PROJECT" --sim "$TMP/sim.json"
