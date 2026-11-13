#!/usr/bin/env bash
# Point this clone at the versioned hooks in .githooks (run once per clone).
set -euo pipefail
cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
echo "hooks installed: pre-push runs scripts/check.sh (skip once with: git push --no-verify)"
