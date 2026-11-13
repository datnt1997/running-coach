#!/usr/bin/env bash
# Read-only: is the instance up, ours, and worth driving? Exit 0 only if all checks pass.
. "$(dirname "$0")/env.sh"
rc=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "ok    $1"; else echo "FAIL  $1"; rc=1; fi; }
chk "db container $DB_CONTAINER running" "[ \"\$(docker inspect -f '{{.State.Running}}' $DB_CONTAINER)\" = true ]"
chk "db reachable on :$DB_PORT" "psql '$VERIFY_DATABASE_URL' -qtAc 'select 1'"
chk "db schema matches app/db/migrations (launch.sh's record)" "diff -q <(cd '$REPO/app/db/migrations' && ls *.sql) '$RUN/migrations.applied'"
chk "server pid file present and process alive" "kill -0 \$(cat '$RUN/server.pid')"
chk ":$APP_PORT is owned by that pid" "lsof -tiTCP:$APP_PORT -sTCP:LISTEN | grep -qx \$(cat '$RUN/server.pid')"
chk "/health ok" "curl -fs $BASE_URL/health"
chk "SPA served at /app" "curl -fs $BASE_URL/app | grep -q '<div id=\"root\"'"
chk "server runs verify_app (fake AI), not app.main" "ps -p \$(cat '$RUN/server.pid') -o command= | grep -q 'uvicorn verify_app:app'"
exit $rc
