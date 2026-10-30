# Requirements — Current-Week Plan UI

## Background

`PlanView.jsx` already renders a full plan as a week-by-week accordion, but nothing tells the
user which week is *actually happening right now*. The user has to know their `start_date` and
count weeks manually. This feature adds a dedicated view that surfaces the current week's
workouts front and center.

This is not a numbered roadmap phase — it's a UI refinement sitting on top of the already-shipped
Phase 1 (goal intake + plan generation). It does not touch Strava, re-planning, or chat (Phases 2–4).

## Scope

**In scope:**
- A new `/app/dashboard` route (home) that shows the current week's workouts for the user's most
  recent `ready` plan.
- Client-side computation of `currentWeek = floor((today - startDate) / 7) + 1`, clamped to
  `[1, totalWeeks]`.
- Empty/edge states: no goals yet, plan still generating, plan generation failed, race day passed
  (`currentWeek > totalWeeks`), plan not yet started (`today < startDate` — show week 1 as "starts
  in N days").
- Nav link to the new dashboard; `GoalForm` moves off `/` to `/new`.
- Backend: expose `startDate` on `GET /goal/{goal_id}/plan`, which is already stored in
  `training_plans.start_date` and already fetched from the DB by `PlanRepository`, but is
  currently dropped in `_build_plan_response` (`app/api/goals.py`) and missing from the
  `PlanResponse` Pydantic model (`app/models/plan.py`). This is a required, minimal backend change
  — it is not purely client-side as first assumed.

**Out of scope:**
- Multiple simultaneous active plans / plan switcher UI (single active plan assumed, per
  `specs/mission.md`).
- Any change to how plans are generated, stored, or re-planned.
- Marking individual workouts as complete/skipped (that's Strava-matching territory, Phase 2/3).
- New frontend dependencies or a test framework (none exists today; frontend stays manually
  validated, consistent with the rest of the app).

## Data / Field Changes

| Field | Where | Change |
|---|---|---|
| `startDate` | `app/models/plan.py: PlanResponse` | **Add** `start_date: date` field |
| `startDate` | `app/api/goals.py: _build_plan_response` | **Add** mapping from `plan["start_date"]` |

No DB schema change — `training_plans.start_date` already exists (migration 002) and is already
selected by `PlanRepository.get_plan_by_goal_id` / `get_plan` (`app/db/repositories.py`).

## Decisions

- **Current-week math lives client-side.** The backend now returns `startDate` and `totalWeeks`
  (already returned); the frontend computes which week is current. No new `current_week` endpoint
  field — keeps the backend response shape stable and avoids coupling "now" to server response
  caching. Revisit if Phase 2 (weekly summaries) or Phase 3 (re-planning) need the same concept
  server-side later.
- **Landing page becomes a dashboard, not the goal form.** `GoalForm` moves to `/new`; `/` (i.e.
  `/app`) becomes the dashboard. This matches "the user already has a plan most of the time" as
  the common case once Phase 1 is in daily use.
- **Single active plan.** Dashboard picks the most recently created goal with `planStatus ===
  'ready'` from `GET /goals` (already sorted by creation per existing repository query — verify
  during implementation, sort client-side by `createdAt` descending if not). No plan-switcher UI.
- **Reuse existing visual language.** Same phase badges (`phase-base`, `phase-build`, etc.), same
  table layout for workouts as `PlanView.jsx`, so the dashboard's "This Week" card looks like a
  zoomed-in `PlanView` week, not a new design system.

## Context

- Follows existing frontend conventions: React Router (`react-router-dom`), plain `fetch`, no
  state management library, inline styles mixed with `App.css` classes (see `GoalHistory.jsx`,
  `PlanView.jsx`).
- Tone: same terse, functional copy as the rest of the app ("Generating your training plan…",
  "No goals yet.") — no marketing language.
- Backend follows existing patterns in `app/api/goals.py` (camelCase aliasing via
  `alias_generator=to_camel` on all Pydantic models).
