#!/usr/bin/env bash
# Apply all migrations with the Runner owner taken from the first entry of
# ALLOWED_EMAILS, so the backfill owner cannot drift from the allowlist.
# Usage: DATABASE_URL=... ALLOWED_EMAILS=you@example.com,other@example.com scripts/migrate_owner.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DATABASE_URL:?set DATABASE_URL}"
: "${ALLOWED_EMAILS:?set ALLOWED_EMAILS (the first entry becomes the owner of existing data)}"

owner=$(printf '%s' "${ALLOWED_EMAILS%%,*}" | tr '[:upper:]' '[:lower:]' | xargs)
[ -n "$owner" ] || { echo "ALLOWED_EMAILS has no first entry" >&2; exit 1; }
echo "Migrating; existing data will be owned by: $owner" >&2

for f in app/db/migrations/*.sql; do
  echo "applying $f" >&2
  PGOPTIONS="-c app.owner_email=$owner" psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
