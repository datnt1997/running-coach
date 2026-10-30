# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (from repo root, with venv active)
pip install -e ".[dev]"

# Start the database
docker compose -f docker/docker-compose.yml up -d

# Run the server (reload on changes)
uvicorn app.main:app --reload

# Start the disposable test database (port 5434, in memory)
docker compose -f docker/docker-compose.yml --profile test up -d db-test

# Run all tests (requires TEST_DATABASE_URL; never uses DATABASE_URL)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5434/running_coach_test pytest

# Run a single test file or test
pytest tests/test_goal_endpoint.py
pytest tests/test_goal_endpoint.py::test_create_goal_and_plan
```

Tests that need a database skip automatically if `TEST_DATABASE_URL` is not set. The `db_pool` fixture drops and recreates all tables on each run, so `tests/conftest.py` ignores `DATABASE_URL` and refuses any test database whose name does not end in `_test`.

## Architecture

This is a **Python/FastAPI** backend. The current implementation uses Anthropic Claude via structured tool use to generate and analyze training plans.

### Request flow

1. `POST /goals` → validates a `GoalRequest` (distance, target time, race date, fitness level)
2. `app/agent/planner.py:generate_plan()` builds a prompt and calls the AI client once with the `generate_training_plan` tool
3. The structured tool-call response is parsed into a `PlanResponse` and persisted via `PlanRepository`
4. Strava sends activity webhooks → `POST /strava/webhook` → background task fetches the full activity, matches it to a planned workout, calls AI with `analyze_activity` tool, and stores an `ActivityAnalysis`
5. After a matched activity, a weekly summary is generated with a plain text AI call (no tool)

### AI abstraction (`app/ai/`)

- `AIClient` (ABC in `client.py`) — the single interface all AI code depends on
- `anthropic_client.py` / `gemini_client.py` — concrete implementations; selected by `AI_PROVIDER` env var
- `factory.py:get_ai_client_dep()` — FastAPI dependency; tests override this via `app.dependency_overrides`
- `tools.py` — provider-agnostic tool schemas (`TOOLS` for plan generation, `ANALYZE_ACTIVITY_TOOL` for activity analysis); each concrete client translates these to its own wire format

### Agent layer (`app/agent/`)

- `prompt.py` — builds all message lists (system + user) for plan generation, activity analysis, and weekly summaries
- `planner.py` — orchestrates plan generation; raises `PlanGenerationError` on malformed tool output
- `analyzer.py` — orchestrates activity analysis and weekly summary generation
- `matching.py` — pure logic (no AI) to match an incoming Strava activity to a planned workout by date + distance (±30% tolerance)
- `validation.py` — input validation for goals

### Database (`app/db/`)

- Connection pool via `psycopg-pool`; `get_db()` yields a single `AsyncConnection` per request
- `migrations/001_initial.sql` — `user_goals`, `training_plans`, `workout_sessions`
- `migrations/002_strava.sql` — adds `start_date` to `training_plans`, plus `strava_connections`, `activity_analyses`, `weekly_summaries`
- `repositories.py` — one repository class per table; all SQL lives here

### Strava integration (`app/strava/` + `app/api/strava.py`)

- OAuth2 PKCE flow: `/strava/connect` → Strava → `/strava/callback` → stores tokens in `strava_connections`
- Webhook: Strava POSTs to `/strava/webhook`; validation challenge is at GET on the same path
- Token refresh is handled transparently in `get_valid_access_token()`
- To register the webhook subscription after deploy: `python scripts/register_strava_webhook.py`

### Testing patterns

- `FakeAIClient` and `FakeAnalysisAIClient` in `conftest.py` return deterministic tool-call responses
- `FakeStravaClient` returns a fixed `ActivityDetail`
- `db_pool` fixture applies both migrations against a real database and tears down at end; tests requiring it skip if `DATABASE_URL` is unset
- `webhook_client` fixture wires both fakes together for end-to-end Strava webhook tests

## Key env vars

| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required when `AI_PROVIDER=anthropic` (default) |
| `DATABASE_URL` | `postgresql://user:pass@host:port/db` |
| `AI_PROVIDER` | `anthropic` (default) or `gemini` |
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | Strava app credentials |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Secret string for webhook handshake |
| `STRAVA_REDIRECT_URI` | Must match Strava app's callback domain setting |
