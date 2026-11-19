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

# Run all tests: starts the disposable test database (port 5434, in memory,
# localhost only) and sets TEST_DATABASE_URL; never uses DATABASE_URL
scripts/test.sh

# Run a single test file or test
scripts/test.sh tests/test_goal_endpoint.py
scripts/test.sh tests/test_goal_endpoint.py::test_create_goal_and_plan

# Everything CI runs (tests + frontend checks); run once per clone to make it
# the pre-push hook
scripts/check.sh
scripts/install-hooks.sh
```

Tests that need a database skip automatically if `TEST_DATABASE_URL` is not set. The `db_pool` fixture drops and recreates all tables on each run, so `tests/conftest.py` ignores `DATABASE_URL` and refuses any test database whose name does not end in `_test`.

## Architecture

This is a **Python/FastAPI** backend. The current implementation uses Anthropic Claude via structured tool use to generate and analyze training plans.

### Request flow

1. `POST /goal` → validates a `GoalRequest` (distance, target time, race date, weekly availability, `vdot`, current `weeklyKm` and `longestRunKm`) and checks it against the scope bounds
2. `app/agent/planner.py:generate_plan()` builds a prompt and calls the AI client once with the `generate_training_plan` tool
3. The structured tool-call response is parsed into a `PlanResponse` and persisted via `PlanRepository`
4. Strava sends activity webhooks → `POST /strava/webhook` → background task fetches the full activity, matches it to a planned workout, calls AI with `analyze_activity` tool, and stores an `ActivityAnalysis`
5. After a matched activity, a weekly summary is generated with a plain text AI call (no tool)

### Fitness assessment (`app/vdot.py` + `app/api/fitness_chat.py`)

- `POST /fitness-chat`: the first turn is a fixed question asking the race distance (no model call). The model then asks the finish time for that distance and collects the other signals, ending with a JSON block (`race_distance`, `race_time`, `weekly_km`, `longest_run_km`). `assess()` validates them (the same limits as `GoalRequest`) and Python computes VDOT and the predicted times; an incomplete block returns `done: false` naming what is missing.
- Runners see only the VDOT and predicted race times. No level or rank is shown: Daniels' levels rate a 1:50 half marathon (VDOT 40) as novice, which does not fit our amateur audience.
- `app/vdot.py`: Daniels-Gilbert VDOT, inverse (race time for a VDOT), `training_paces` (E, M, T, I paces per km from a VDOT, checked against Table 5.2; they go into the plan prompt so the model never invents paces), `break_factor` (Table 15.1).
- `frontend/src/lib/vdot.js` mirrors the formula for manual entry (VDOT shown to one decimal, as in the chat); `npm run check:vdot` keeps it in step.
- Source notes and page references: `specs/2026-11-03-vdot-level-assessment/research.md`. How to search `references/daniels.txt` (Vietnamese, page-number rule): `specs/2026-11-13-weekly-availability-and-missed-workouts/research.md`. The book PDF is git-ignored and copyrighted.

### Sign-in (`app/auth.py` + `app/api/auth.py`)

- `POST /auth/google` takes a Google ID token (`credential`), checks it through `GoogleVerifier` (tokeninfo endpoint; tests inject a fake through `get_google_verifier`), checks the email against `ALLOWED_EMAILS`, and sets a signed session cookie. `GET /auth/me` says who is signed in; `POST /auth/logout` clears it. The session is stateless (no table); the allowlist is re-checked on every request.
- Ownership: the `runners` table (one row per email, created on first request after sign-in) owns every Goal, Plan, Strava connection, Activity analysis and Weekly summary through a NOT NULL `runner_id`. Every repository takes `runner_id` in its constructor and scopes all SQL by it; routes get it from the `require_runner` dependency. The Strava webhook finds the Runner with `RunnerRepository.find_by_strava_athlete`; an unknown athlete gets a 200 and nothing changes. A new owned table needs `runner_id`, scoped repository queries and a case in `tests/test_runner_ownership.py`.
- Migration 009 backfills the first Runner from `app.owner_email` (required when the database already has rows). Run `scripts/migrate_owner.sh` (reads `DATABASE_URL` and `ALLOWED_EMAILS` from the environment or `.env`; applies only 009 unless you pass files): it takes the owner from the first `ALLOWED_EMAILS` entry so the owner cannot silently differ from the allowlist. Raw alternative: `PGOPTIONS="-c app.owner_email=you@example.com" psql "$DATABASE_URL" -f app/db/migrations/009_runner_ownership.sql`.
- `require_session` guards every data, chat and Strava status/connect/callback/disconnect route (401 without a session). Open: `/health`, `/`, `/auth/google`, `/auth/logout`, and the Strava webhook (GET challenge and POST). `tests/test_auth.py` enumerates the OpenAPI paths, so a new route must be guarded or added to its `OPEN_ROUTES` list.
- Tests: the `client` and `webhook_client` fixtures are signed in as an allowlisted fake runner; `anon_client` and `anon_webhook_client` have no session.

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
- `validation.py` — scope bounds: fastest supported time per distance, minimum weeks to the race (`specs/mission.md`)

### Plan import (`app/api/plan_import.py` + `app/agent/plan_import.py`)

- `POST /plan/import` (signed in; no UI) takes `distance`, `targetTime`, `raceDate`, `startDate` (a Monday, first day of week 1) and `csv`: a header row `week,phase,day,type,distance_km[,pace_zone,notes]` then one row per Planned workout, comma or tab separated. It creates an Active Goal (status `ready`) with its Plan in one transaction; any bad row returns 422 with `rows: [{line, message}]` and writes nothing.
- The target-time and six-week bounds in `validation.py` do not apply to an import; they still guard `POST /goal`. Weekly availability is derived from the days the Plan uses; VDOT from the target time.

### Database (`app/db/`)

- Connection pool via `psycopg-pool`; `get_db()` yields a single `AsyncConnection` per request
- `migrations/NNN_name.sql` — applied in filename order; tests and the verify skill glob the directory, so a new file needs no registration
- `repositories.py` — one repository class per table; all SQL lives here

### Strava integration (`app/strava/` + `app/api/strava.py`)

- OAuth2 PKCE flow: `/strava/connect` → Strava → `/strava/callback` → stores tokens in `strava_connections`
- Webhook: Strava POSTs to `/strava/webhook`; validation challenge is at GET on the same path
- Token refresh is handled transparently in `get_valid_access_token()`
- To register the webhook subscription after deploy: `python scripts/register_strava_webhook.py`

### Testing patterns

- `FakeAIClient` and `FakeAnalysisAIClient` in `conftest.py` return deterministic tool-call responses
- `FakeStravaClient` returns a fixed `ActivityDetail`
- `db_pool` fixture applies all migrations against a real database and tears down at end
- `webhook_client` fixture wires both fakes together for end-to-end Strava webhook tests

## Key env vars

| Var | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required when `AI_PROVIDER=anthropic` (default) |
| `CHAT_AI_PROVIDER` | Provider for `POST /fitness-chat` only; falls back to `AI_PROVIDER` |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Required when a selected provider is `gemini`; model defaults to `gemini-2.0-flash` |
| `DATABASE_URL` | `postgresql://user:pass@host:port/db` |
| `AI_PROVIDER` | `anthropic` (default) or `gemini` |
| `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` | Strava app credentials |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Secret string for webhook handshake |
| `STRAVA_REDIRECT_URI` | Must match Strava app's callback domain setting |
| `GOOGLE_CLIENT_ID` | Google OAuth client id; the ID token's audience must match. The SPA reads the same value at build time as `VITE_GOOGLE_CLIENT_ID` |
| `ALLOWED_EMAILS` | Comma-separated emails allowed to sign in (case-insensitive); others get 403 |
| `SESSION_SECRET` | Signs the session cookie (HttpOnly, SameSite=Lax, one year); signing refuses an empty value |
| `COOKIE_SECURE` | Session cookie `Secure` flag; defaults to true. Set `false` for local development over plain http, or the browser drops the cookie |

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `datnt1997/running-coach` (via the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
