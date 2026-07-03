# Phase 1 — Goal Intake + Static Plan Generation: Requirements

## Scope

Build the end-to-end path from a user submitting their goal to receiving a personalized, periodized training plan. No Strava, no re-planning, no chat — just intake → generate → persist → retrieve.

## In Scope

- `POST /goal` — accept user goal, validate bounds, persist the goal to `user_goals`, immediately return an acceptance response; plan generation runs in the background.
- `GET /goal/{goal_id}/plan` — poll for the generated plan by `goal_id`; returns 202 while pending, 200 with the full plan once ready.
- `GET /goals` — list all submitted goals with their current status and basic metadata.
- `DELETE /goal/{goal_id}` — delete a goal and its associated training plan and workouts.
- Goal validation: reject or warn when target time exceeds supported bounds.
- AI client (`AIClient` abstraction, default provider: Claude Sonnet 4.6) generates a periodized plan (base → build → peak → taper) using sports-science principles.
- PostgreSQL schema: `user_goals` + `workout_plans` tables (row-per-workout model).
- Pydantic v2 request/response models with strict validation.
- React (Vite) frontend served as static files by FastAPI; supports submit goal, view plan with live polling, goal history list, and delete.

## Out of Scope (Phase 1)

- Authentication / user accounts — single-user, no auth required.
- Strava integration.
- Plan adaptation or re-planning.
- Chat or conversational interface.

## API Contract

### `POST /goal`

**Request body:**
```json
{
  "distance": "half_marathon",       // "half_marathon" | "full_marathon"
  "targetTime": "1:55:00",           // HH:MM:SS string
  "raceDate": "2026-10-18",          // ISO date, must be ≥ 10 weeks from today
  "fitnessLevel": "intermediate",    // "beginner" | "intermediate" | "advanced"
  "daysPerWeek": 4,                  // 3–7
  "injuryHistory": "left knee tendinopathy"  // free text, nullable
}
```

**Acceptance response (202):** returned immediately after the goal is persisted; plan generation has been queued.
```json
{
  "goalId": "<uuid>",
  "status": "generating"
}
```

**Error response (422) — goal out of bounds:**
```json
{
  "error": "goal_out_of_scope",
  "message": "Target time 1:38:00 is faster than the supported ceiling for half marathon (1:44:00). This agent is not designed for elite-level plans."
}
```

---

### `GET /goal/{goal_id}/plan`

Poll this endpoint after receiving the 202. Returns 202 while the background task is still running, 200 once the plan is ready.

**Still generating (202):**
```json
{
  "goalId": "<uuid>",
  "status": "generating"
}
```

**Ready (200):**
```json
{
  "planId": "<uuid>",
  "goalId": "<uuid>",
  "status": "ready",
  "summary": "16-week Half Marathon plan targeting sub-1:55 ...",
  "totalWeeks": 16,
  "phaseBreakdown": {
    "base": 6,
    "build": 5,
    "peak": 3,
    "taper": 2
  },
  "weeks": [
    {
      "weekNumber": 1,
      "phase": "base",
      "workouts": [
        { "day": "Mon", "type": "easy", "distanceKm": 8.0, "paceZone": "Z2", "notes": "Conversational pace" },
        { "day": "Wed", "type": "tempo", "distanceKm": 6.0, "paceZone": "Z3", "notes": "Comfortably hard" },
        { "day": "Sat", "type": "long", "distanceKm": 14.0, "paceZone": "Z2", "notes": "Easy effort" },
        { "day": "Sun", "type": "recovery", "distanceKm": 5.0, "paceZone": "Z1", "notes": "Very easy" }
      ]
    }
  ]
}
```

**Failed (200):**
```json
{
  "goalId": "<uuid>",
  "status": "failed",
  "error": "plan_generation_failed"
}
```

---

### `GET /goals`

Returns all submitted goals, newest first.

**Response (200):**
```json
{
  "goals": [
    {
      "goalId": "<uuid>",
      "distance": "half_marathon",
      "targetTime": "1:55:00",
      "raceDate": "2026-10-18",
      "fitnessLevel": "intermediate",
      "daysPerWeek": 4,
      "planStatus": "ready",
      "createdAt": "2026-06-21T09:00:00Z"
    }
  ]
}
```

`planStatus` is one of `"generating"`, `"ready"`, `"failed"`.

---

### `DELETE /goal/{goal_id}`

Deletes the goal and all related rows (`training_plans`, `workout_sessions`) in a single transaction.

**Response (200):**
```json
{ "deleted": true }
```

**Not found (404):**
```json
{ "error": "goal_not_found", "message": "Goal not found" }
```

---

## UI (React + Vite)

Served as static files from `frontend/dist/` by FastAPI (`GET /app/{path}` + index fallback). In development, Vite dev server proxies `/api` requests to FastAPI on port 8000.

### Pages / views

| View | Route | Description |
|---|---|---|
| Goal form | `/app` | Form to submit a new goal; shows inline validation errors (422) and redirects to the plan view on 202 |
| Plan view | `/app/goals/:goalId` | Polls `GET /goal/{goalId}/plan` every 3 s while `status === "generating"`; renders the week-by-week plan once ready; shows an error state on `"failed"` |
| Goal history | `/app/history` | Lists all goals via `GET /goals`; each row links to its plan view and has a delete button |

### Goal form fields

| Field | Input type | Validation (client-side) |
|---|---|---|
| Distance | Select (`half_marathon` / `full_marathon`) | Required |
| Target time | Text (`HH:MM:SS`) | Required, format check |
| Race date | Date picker | Required, must be ≥ 10 weeks from today |
| Fitness level | Select (`beginner` / `intermediate` / `advanced`) | Required |
| Days per week | Number (3–7) | Required |
| Injury history | Textarea | Optional |

---

## Goal Validation Rules

| Distance | Fastest supported | Action if exceeded |
|---|---|---|
| Half Marathon | 1:44:00 | Return 422 with `goal_out_of_scope` |
| Full Marathon | 3:59:00 | Return 422 with `goal_out_of_scope` |

Minimum race date lead time: 10 weeks from `POST /goal` date (plan cannot be generated if race is too soon).

## Database Schema (row-per-workout)

```sql
-- user goals
CREATE TABLE user_goals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distance    TEXT NOT NULL,           -- 'half_marathon' | 'full_marathon'
    target_time INTERVAL NOT NULL,
    race_date   DATE NOT NULL,
    fitness_level TEXT NOT NULL,
    days_per_week INT NOT NULL,
    injury_history TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- plan metadata
CREATE TABLE training_plans (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id     UUID REFERENCES user_goals(id),
    total_weeks INT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- individual workouts
CREATE TABLE workout_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID REFERENCES training_plans(id),
    week_number INT NOT NULL,
    phase       TEXT NOT NULL,           -- 'base' | 'build' | 'peak' | 'taper'
    day_of_week TEXT NOT NULL,           -- 'Mon' | 'Tue' | ...
    workout_type TEXT NOT NULL,          -- 'easy' | 'tempo' | 'long' | 'interval' | 'recovery' | 'rest'
    distance_km NUMERIC(5,2),
    pace_zone   TEXT,                    -- 'Z1'–'Z5'
    notes       TEXT
);
```

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Intake flow | Single `POST /goal` | Simpler contract; multi-turn adds state complexity with no Phase 1 benefit |
| Plan generation | Background task | AI call is slow (~5–15 s); returning 202 immediately gives a better UX |
| Plan polling | Client-side poll every 3 s | Simpler than WebSockets for a single-user tool; acceptable latency |
| Plan storage | Row-per-workout | Queryable for Phase 2 Strava comparison; diffable for Phase 3 re-planning |
| AI client | `AIClient` abstraction (default: Claude Sonnet 4.6) | Provider-swappable; Claude chosen for JSON schema adherence and sports-physiology domain knowledge |
| Frontend | React + Vite, served as static files by FastAPI | No separate server to manage; Vite proxy covers local dev |
| Auth | None | Single-user tool; auth is Phase 5+ scope |
| Done bar | Working UI + integration tests against real Postgres | Smoke-test the form → generating → plan-ready flow end-to-end |

## Constraints from Tech Stack

- Backend: Python 3.12+, FastAPI, Pydantic v2.
- Frontend: React 18+, Vite, plain CSS (no UI library dependency).
- `ANTHROPIC_API_KEY`, `DATABASE_URL`, `AI_PROVIDER` loaded via `python-dotenv`.
- Default AI provider: `anthropic` with model `claude-sonnet-4-6`; override via `AI_PROVIDER=gemini`.
