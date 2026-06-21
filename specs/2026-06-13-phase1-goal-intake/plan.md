# Phase 1 — Goal Intake + Static Plan Generation: Implementation Plan

## Group 1 — Project Bootstrap

1.1 Create directory structure: `app/`, `app/api/`, `app/models/`, `app/db/`, `app/agent/`, `app/ai/`, `tests/`
1.2 Add `pyproject.toml` (or `requirements.txt`) with dependencies: `fastapi`, `uvicorn`, `anthropic`, `asyncpg` (or `psycopg[binary]`), `pydantic`, `python-dotenv`, `pytest`, `httpx`; add `google-generativeai` as optional for Gemini provider
1.3 Create `.env.example` documenting `ANTHROPIC_API_KEY`, `DATABASE_URL`, and `AI_PROVIDER` (default: `anthropic`)
1.4 Create `app/config.py` — loads and validates env vars via `python-dotenv` at startup; raises on missing required keys

---

## Group 2 — Database Layer

2.1 Write `app/db/migrations/001_initial.sql` — `user_goals`, `training_plans`, `workout_sessions` tables (schema from requirements.md)
2.2 Create `app/db/connection.py` — async Postgres connection pool (asyncpg or psycopg3 async); `get_db()` dependency for FastAPI
2.3 Create `app/db/repositories.py` — `GoalRepository` and `PlanRepository` with typed insert/select methods; no raw SQL in route handlers

---

## Group 3 — Pydantic Models

3.1 `app/models/goal.py` — `GoalRequest` (intake fields + validators for distance enum, target_time format, race_date lead time, days_per_week range)
3.2 `app/models/plan.py` — `WorkoutSession`, `PlanWeek`, `PlanResponse` matching the API contract in requirements.md
3.3 Add `GoalValidationError` model for structured 422 responses

---

## Group 4 — Goal Validation

4.1 `app/agent/validation.py` — `validate_goal(goal: GoalRequest) -> None` raises `GoalOutOfScopeError` for:
  - HM target faster than 1:45:00
  - FM target faster than 4:00:00
  - Race date less than 10 weeks from today
4.2 Unit tests for all validation edge cases (exact boundary, 1 second over, 1 second under)

---

## Group 5 — AI Client + Plan Generation

5.1 `app/ai/client.py` — `AIClient` abstract base class with `generate(messages, tools=None, response_format=None) -> AIResponse`; `AIResponse` dataclass: `{content: str, tool_calls: list[ToolCall], usage: TokenUsage}`
5.2 `app/ai/anthropic_client.py` — `AnthropicClient(AIClient)` wrapping the Anthropic SDK; translates `AIResponse` to/from Anthropic tool-use format
5.3 `app/ai/gemini_client.py` — `GeminiClient(AIClient)` wrapping `google-generativeai`; translates `AIResponse` to/from Gemini function-calling format
5.4 `app/ai/tools.py` — provider-agnostic tool definitions (schema); each client adapter translates to its provider's format at call time
5.5 `app/ai/factory.py` — `get_ai_client() -> AIClient` reads `AI_PROVIDER` env var and returns the appropriate client
5.6 `app/agent/prompt.py` — build the system + user prompt for plan generation; includes periodization guidelines (base/build/peak/taper ratios, zone definitions, weekly mileage progression cap at 10%)
5.7 `app/agent/planner.py` — `generate_plan(goal: GoalRequest) -> PlanResponse`
  - Calls `get_ai_client().generate(...)` with structured output (JSON schema matching `PlanResponse`)
  - Parses and validates response with Pydantic
  - Raises `PlanGenerationError` on malformed output
5.8 Manual smoke test: call `generate_plan()` directly in a script and print output

---

## Group 6 — API Endpoints

6.1 `app/api/goals.py` — `POST /goal` route:
  - Validate request with `GoalRequest`
  - Call `validate_goal()`; return 422 on failure
  - Persist goal via `GoalRepository.insert()` — this is the only synchronous DB write
  - Enqueue `_generate_plan_background(goal_id, goal, ai_client)` as a `BackgroundTask`
  - Return HTTP 202 immediately: `{ "goalId": "<uuid>", "status": "generating" }`
6.2 `app/api/goals.py` — `_generate_plan_background` background task:
  - Call `generate_plan(goal, client)`
  - Persist plan + workouts via `PlanRepository`
  - On `PlanGenerationError`: update `user_goals.plan_status = 'failed'` and log the error
  - On success: update `user_goals.plan_status = 'ready'`
6.3 `app/api/goals.py` — `GET /goal/{goal_id}/plan` route:
  - Read `user_goals.plan_status` for the given `goal_id`
  - If `generating`: return 202 `{ "goalId", "status": "generating" }`
  - If `failed`: return 200 `{ "goalId", "status": "failed", "error": "plan_generation_failed" }`
  - If `ready`: load plan + workouts via `PlanRepository` and return 200 `PlanResponse` with `"status": "ready"`
  - If `goal_id` not found: return 404
6.4 `app/api/goals.py` — `GET /goals` route:
  - Query all rows from `user_goals` ordered by `created_at DESC`
  - Return list with `goalId`, `distance`, `targetTime`, `raceDate`, `fitnessLevel`, `daysPerWeek`, `planStatus`, `createdAt`
6.5 `app/api/goals.py` — `DELETE /goal/{goal_id}` route:
  - Delete `workout_sessions`, `training_plans`, `user_goals` in a single transaction (cascade via FK or explicit order)
  - Return 200 `{ "deleted": true }` or 404 if not found
6.6 `app/db/migrations/` — add `plan_status TEXT NOT NULL DEFAULT 'generating'` column to `user_goals`
6.7 `app/main.py` — FastAPI app wiring, include routers, startup/shutdown lifespan for DB pool; mount `frontend/dist` as static files at `/app`

---

## Group 7 — React Frontend

7.1 Scaffold with Vite: `npm create vite@latest frontend -- --template react`; configure `vite.config.js` to proxy `/goal`, `/goals`, `/strava` to `http://localhost:8000`
7.2 `frontend/src/pages/GoalForm.jsx` — controlled form for all goal fields; client-side validation before submit; on 202 navigate to `/app/goals/:goalId`; display 422 errors inline
7.3 `frontend/src/pages/PlanView.jsx` — on mount call `GET /goal/:goalId/plan`; if `status === "generating"` show spinner and retry every 3 s; on `"ready"` render week-by-week plan table; on `"failed"` show error message
7.4 `frontend/src/pages/GoalHistory.jsx` — fetch `GET /goals` on mount; render table with `distance`, `targetTime`, `raceDate`, `planStatus`, link to plan view, and a delete button that calls `DELETE /goal/:goalId` then refreshes the list
7.5 `frontend/src/App.jsx` — React Router v6 routes: `/app` → `GoalForm`, `/app/goals/:goalId` → `PlanView`, `/app/history` → `GoalHistory`; nav bar with links to form and history
7.6 `npm run build` outputs to `frontend/dist/`; FastAPI mounts this at `/app` so the single-user tool works from one `uvicorn` process

---

## Group 8 — Integration Test

8.1 `tests/test_goal_endpoint.py`:
  - Test: valid HM goal → 202 with `{ "goalId", "status": "generating" }`; poll `GET /goal/{goalId}/plan` until 200 + full plan structure (4 phases, ≥10 weeks, all workouts have required fields)
  - Test: valid FM goal → 202; poll until 200 `totalWeeks >= 12`
  - Test: HM goal faster than 1:45:00 → 422 `goal_out_of_scope` (no background task queued)
  - Test: FM goal faster than 4:00:00 → 422 `goal_out_of_scope`
  - Test: race date < 10 weeks → 422
  - Test: `GET /goal/{unknown_uuid}/plan` → 404
  - Test: `GET /goals` → 200 list including the submitted goal
  - Test: `DELETE /goal/{goalId}` → 200; subsequent `GET /goal/{goalId}/plan` → 404
8.2 Tests hit real local Postgres (no mocks on DB); use `httpx.AsyncClient` against the FastAPI app
8.3 Add `tests/conftest.py` with DB setup/teardown fixtures (create tables before, drop after)
