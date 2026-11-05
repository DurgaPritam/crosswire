#!/usr/bin/env bash
# Creates .venv (Python 3.11+) with requirements-dev.txt if it's missing. Used by `just test`, `just console*`, `just notary`.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/bin/python ] && .venv/bin/python -c "import httpx, pytest" 2>/dev/null; then exit 0; fi
py="$(command -v python3.12 || command -v python3.13 || command -v python3.11 || command -v python3 || true)"
[ -n "$py" ] || { echo "error: Python 3.11+ not found (install it, e.g. brew install python@3.12)" >&2; exit 1; }
"$py" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || { echo "error: $py is older than 3.11" >&2; exit 1; }
echo "creating .venv with $("$py" --version) from requirements-dev.txt (one time)"
"$py" -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
