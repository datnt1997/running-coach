# Sourced by the other scripts. Everything here is isolated from the dev stack
# (dev DB is :5433, dev server :8000, test DB :5434).
REPO=$(git rev-parse --show-toplevel)
SKILL="$REPO/.claude/skills/verify-running-coach"
RUN="${VERIFY_RUN_DIR:-${TMPDIR:-/tmp}/running-coach-verify}"
EVIDENCE="${VERIFY_EVIDENCE_DIR:-$RUN/evidence}"   # cleanup never touches this
DB_CONTAINER=running-coach-verify-db
DB_PORT=5441
APP_PORT=8010
export VERIFY_DATABASE_URL="postgresql://postgres:verify@127.0.0.1:$DB_PORT/running_coach_verify"
BASE_URL="http://127.0.0.1:$APP_PORT"
