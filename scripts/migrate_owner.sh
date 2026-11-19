#!/usr/bin/env bash
# Apply the Runner ownership migration (009) with the owner taken from the first
# entry of ALLOWED_EMAILS, so the backfill owner cannot drift from the allowlist.
# DATABASE_URL and ALLOWED_EMAILS come from the environment, or from .env at the repo root.
# Usage: scripts/migrate_owner.sh [migration.sql ...]   (default: 009_runner_ownership.sql only;
# earlier migrations are not idempotent, so pass them only for a fresh database)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${DATABASE_URL:?set DATABASE_URL (environment or .env)}"
: "${ALLOWED_EMAILS:?set ALLOWED_EMAILS (the first entry becomes the owner of existing data)}"

owner=$(printf '%s' "${ALLOWED_EMAILS%%,*}" | tr '[:upper:]' '[:lower:]' | xargs)
[ -n "$owner" ] || { echo "ALLOWED_EMAILS has no first entry" >&2; exit 1; }
echo "Migrating; existing data will be owned by: $owner" >&2

files=("$@")
[ ${#files[@]} -gt 0 ] || files=(app/db/migrations/009_runner_ownership.sql)

for f in "${files[@]}"; do
  echo "applying $f" >&2
  PGOPTIONS="-c app.owner_email=$owner" psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
