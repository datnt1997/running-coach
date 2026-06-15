# Phase 1 — Goal Intake + Static Plan Generation: Requirements

## Scope

Build the end-to-end path from a user submitting their goal to receiving a personalized, periodized training plan. No Strava, no re-planning, no chat — just intake → generate → persist → retrieve.

## In Scope

- `POST /goal` — accept user goal, validate bounds, invoke the AI client to generate a plan, persist to Postgres, return plan JSON + human-readable summary.
- `GET /plan` — retrieve a stored plan by `plan_id`.
- Goal validation: reject or warn when target time exceeds supported bounds.
- AI client (`AIClient` abstraction, default provider: Claude Sonnet 4.6) generates a periodized plan (base → build → peak → taper) using sports-science principles.
- PostgreSQL schema: `user_goals` + `workout_plans` tables (row-per-workout model).
- Pydantic v2 request/response models with strict validation.

## Out of Scope (Phase 1)

- Authentication / user accounts — single-user, no auth required.
- Strava integration.
- Plan adaptation or re-planning.
- Chat or conversational interface.
- Any frontend / UI.

## API Contract

### `POST /goal`

**Request body:**
```json
{
  "distance": "half_marathon",       // "half_marathon" | "full_marathon"
  "target_time": "1:55:00",          // HH:MM:SS string
  "race_date": "2026-10-18",         // ISO date, must be ≥ 10 weeks from today
  "fitness_level": "intermediate",   // "beginner" | "intermediate" | "advanced"
  "days_per_week": 4,                // 3–6
  "injury_history": "left knee tendinopathy"  // free text, nullable
}
```

**Success response (200):**
```json
{
  "plan_id": "<uuid>",
  "goal_id": "<uuid>",
  "summary": "16-week Half Marathon plan targeting sub-1:55 ...",
  "total_weeks": 16,
  "phase_breakdown": {
    "base": 6,
    "build": 5,
    "peak": 3,
    "taper": 2
  },
  "weeks": [
    {
      "week_number": 1,
      "phase": "base",
      "workouts": [
        { "day": "Mon", "type": "easy", "distance_km": 8.0, "pace_zone": "Z2", "notes": "Conversational pace" },
        { "day": "Wed", "type": "tempo", "distance_km": 6.0, "pace_zone": "Z3", "notes": "Comfortably hard" },
        { "day": "Sat", "type": "long", "distance_km": 14.0, "pace_zone": "Z2", "notes": "Easy effort" },
        { "day": "Sun", "type": "recovery", "distance_km": 5.0, "pace_zone": "Z1", "notes": "Very easy" }
      ]
    }
  ]
}
```

**Error response (422) — goal out of bounds:**
```json
{
  "error": "goal_out_of_scope",
  "message": "Target time 1:38:00 is faster than the supported ceiling for half marathon (sub 1:45:00). This agent is not designed for elite-level plans."
}
```

### `GET /plan/{plan_id}`

Returns the same shape as the `POST /goal` success response.

## Goal Validation Rules

| Distance | Fastest supported | Action if exceeded |
|---|---|---|
| Half Marathon | 1:45:00 | Return 422 with `goal_out_of_scope` |
| Full Marathon | 4:00:00 | Return 422 with `goal_out_of_scope` |

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
| Plan storage | Row-per-workout | Queryable for Phase 2 Strava comparison; diffable for Phase 3 re-planning |
| Plan generation | `AIClient` abstraction (default: Claude Sonnet 4.6) | Provider-swappable; Claude chosen for JSON schema adherence and sports-physiology domain knowledge |
| Auth | None | Single-user tool; auth is Phase 5+ scope |
| Done bar | API contract + integration test | No UI required; integration test against real local Postgres is sufficient |

## Constraints from Tech Stack

- Python 3.12+, FastAPI, Pydantic v2.
- `ANTHROPIC_API_KEY`, `DATABASE_URL`, `AI_PROVIDER` loaded via `python-dotenv`.
- Default AI provider: `anthropic` with model `claude-sonnet-4-6`; override via `AI_PROVIDER=gemini`.
