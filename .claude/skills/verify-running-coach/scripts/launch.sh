#!/usr/bin/env bash
# Start a disposable Postgres (tmpfs) + the real app with a faked AI client.
# Ready = migrations applied AND /health answers AND /app serves the SPA.
set -euo pipefail
. "$(dirname "$0")/env.sh"
mkdir -p "$RUN" "$EVIDENCE"

docker info >/dev/null 2>&1 || { echo "Docker daemon is not running (try: open -a Docker)"; exit 1; }
if docker ps -a --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "$DB_CONTAINER already exists: run cleanup.sh first (or doctor.sh to inspect)"; exit 1
fi
if lsof -iTCP:$APP_PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "port $APP_PORT is taken by something this run did not start"; exit 1
fi

# The compose project label only groups the container under postgres-running-coach in
# Docker Desktop; it is not managed by compose, and cleanup.sh still removes it by name.
docker run -d --name "$DB_CONTAINER" -e POSTGRES_PASSWORD=verify -e POSTGRES_DB=running_coach_verify \
  --label com.docker.compose.project=postgres-running-coach \
  --tmpfs /var/lib/postgresql/data -p 127.0.0.1:$DB_PORT:5432 postgres:16 >/dev/null

# TCP only opens after the image's init scripts finish, so a successful query means usable.
for i in $(seq 1 60); do
  psql "$VERIFY_DATABASE_URL" -qtAc 'select 1' >/dev/null 2>&1 && break
  sleep 1
  [ "$i" = 60 ] && { echo "database never became usable"; exit 1; }
done
for f in "$REPO"/app/db/migrations/*.sql; do
  psql "$VERIFY_DATABASE_URL" -q -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done
# doctor.sh compares this record with the directory to spot a stale schema.
(cd "$REPO/app/db/migrations" && ls *.sql) >"$RUN/migrations.applied"

# Build the SPA when dist is missing or older than any source file.
if [ ! -f "$REPO/frontend/dist/index.html" ] || [ -n "$(find "$REPO/frontend/src" "$REPO/frontend/index.html" -newer "$REPO/frontend/dist/index.html" -print -quit)" ]; then
  [ -d "$REPO/frontend/node_modules" ] || (cd "$REPO/frontend" && npm ci >"$RUN/npm-ci.log" 2>&1) || { echo "npm ci failed, see $RUN/npm-ci.log"; exit 1; }
  (cd "$REPO/frontend" && npm run build >"$RUN/build.log" 2>&1) || { echo "frontend build failed, see $RUN/build.log"; exit 1; }
fi

# Process env wins over .env (load_dotenv does not override), so the dev DB and real keys are never used.
cd "$REPO"
DATABASE_URL="$VERIFY_DATABASE_URL" ANTHROPIC_API_KEY=verify-unused AI_PROVIDER=anthropic APP_LANGUAGE=vi \
STRAVA_CLIENT_ID=verify STRAVA_CLIENT_SECRET=verify STRAVA_WEBHOOK_VERIFY_TOKEN=verify \
STRAVA_REDIRECT_URI="$BASE_URL/strava/callback" \
nohup "$REPO/.venv/bin/python" -m uvicorn verify_app:app --app-dir "$SKILL/scripts" \
  --host 127.0.0.1 --port $APP_PORT >"$RUN/server.log" 2>&1 &
echo $! >"$RUN/server.pid"

for i in $(seq 1 30); do
  curl -fs "$BASE_URL/health" >/dev/null 2>&1 && curl -fs "$BASE_URL/app" | grep -q '<div id="root"' && { echo "ready: $BASE_URL/app (evidence dir: $EVIDENCE)"; exit 0; }
  sleep 1
done
echo "server not ready, tail of $RUN/server.log:"; tail -20 "$RUN/server.log"; exit 1
