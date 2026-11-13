#!/usr/bin/env bash
# Run pytest against the disposable test database (compose profile "test").
# Starts the container if needed and sets TEST_DATABASE_URL from the same
# defaults docker-compose.yml uses. Extra arguments go to pytest.
set -euo pipefail
cd "$(dirname "$0")/.."

user=${POSTGRES_USER:-postgres}
password=${POSTGRES_PASSWORD:-postgres}
port=${POSTGRES_TEST_PORT:-5434}
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://$user:$password@localhost:$port/running_coach_test}"

docker compose -f docker/docker-compose.yml --profile test up -d --wait db-test >/dev/null

pytest_bin=pytest
[ -x .venv/bin/pytest ] && pytest_bin=.venv/bin/pytest
exec "$pytest_bin" "$@"
