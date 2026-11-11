#!/usr/bin/env bash
# Tear down only what launch.sh started. Evidence ($EVIDENCE) is kept.
. "$(dirname "$0")/env.sh"
if [ -f "$RUN/server.pid" ]; then kill "$(cat "$RUN/server.pid")" 2>/dev/null || true; rm -f "$RUN/server.pid"; fi
docker rm -f "$DB_CONTAINER" >/dev/null 2>&1 || true
echo "cleaned; evidence kept at $EVIDENCE"
