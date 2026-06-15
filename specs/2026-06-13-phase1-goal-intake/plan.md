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
  - Call `validate_goal()`
  - Call `generate_plan()`
  - Persist goal + plan via repositories
  - Return `PlanResponse`
6.2 `app/api/plans.py` — `GET /plan/{plan_id}` route:
  - Load plan + workouts from DB
  - Return `PlanResponse`
6.3 `app/main.py` — FastAPI app wiring, include routers, startup/shutdown lifespan for DB pool

---

## Group 7 — Integration Test

7.1 `tests/test_goal_endpoint.py`:
  - Test: valid HM goal → 200 + plan with correct structure (4 phases, ≥10 weeks, all workouts have required fields)
  - Test: valid FM goal → 200
  - Test: HM goal faster than 1:45:00 → 422 `goal_out_of_scope`
  - Test: FM goal faster than 4:00:00 → 422 `goal_out_of_scope`
  - Test: race date < 10 weeks → 422
  - Test: `GET /plan/{plan_id}` → returns same plan
7.2 Tests hit real local Postgres (no mocks on DB); use `httpx.AsyncClient` against the FastAPI app
7.3 Add `tests/conftest.py` with DB setup/teardown fixtures (create tables before, drop after)
