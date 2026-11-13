#!/usr/bin/env bash
# Everything CI runs, locally: the Python tests and the frontend checks.
# Used by .githooks/pre-push.
set -euo pipefail
cd "$(dirname "$0")/.."

scripts/test.sh -q
python_bin=python3
[ -x .venv/bin/python ] && python_bin=.venv/bin/python
"$python_bin" scripts/check_glossary.py
(cd frontend && npm run -s check:i18n && npm run -s check:vdot && npm run -s check:availability)
