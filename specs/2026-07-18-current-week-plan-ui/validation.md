# Validation — Current-Week Plan UI

## Automated

- `pytest` passes in full (requires `DATABASE_URL` set; see root `CLAUDE.md`).
- `tests/test_goal_endpoint.py` new/updated assertions pass:
  - `GET /goal/{goal_id}/plan` response includes `startDate` when `status == "ready"`.
  - `startDate` is a valid ISO `YYYY-MM-DD` string parseable by `date.fromisoformat`.
- No regressions in existing goal/plan/Strava webhook tests (`test_goal_endpoint.py`,
  `test_matching.py`, `test_strava_webhook.py`).
- Backend type-correctness: `PlanResponse` still validates via Pydantic with the new field
  required (not optional) — a plan row without `start_date` should not occur since the column has
  been populated since migration 002, but confirm `PlanRepository.insert_plan` always supplies it
  (it defaults to `date.today()` per `app/db/repositories.py:114-115`, so it's never null).

## Manual

1. **Fresh user, no goals** — visit `/app` (`/`): dashboard shows "No training plan yet." + link
   to `/app/new`.
2. **Plan generating** — submit a goal, immediately visit dashboard: shows the same spinner/copy
   pattern as `PlanView.jsx` ("Generating your training plan…").
3. **Plan ready, mid-training** — with a plan whose `start_date` is ~2 weeks in the past, dashboard
   shows the correct current week's workouts (cross-check the week number against manual
   `floor((today - start_date)/7)+1` math).
4. **Plan ready, not started yet** — plan with `start_date` a few days in the future: dashboard
   shows week 1 with an "upcoming" banner and correct day count.
5. **Plan ready, race day passed** — plan whose last week is in the past: dashboard shows final
   week with a "finished" banner, doesn't crash or show a blank week.
6. **Plan failed** — goal whose generation failed: dashboard shows the failure state with a link to
   retry via `/app/new`.
7. **Navigation** — nav bar correctly links: dashboard (`/`), "New Goal" (`/new`), "History"
   (`/history`); `GoalHistory`'s "+ New Goal" button lands on the form, not the dashboard.
8. **"Full plan →" link** — from the dashboard's This Week card, clicking through lands on the
   existing `PlanView.jsx` for that goal, with the same week visible/expanded.
9. **Multiple goals** — create two goals; confirm dashboard picks the most recently created
   `ready` one, not an older one.

## Tone check

- Empty/edge-state copy matches existing terse style ("No goals yet.", "Generating your training
  plan…") — no exclamation marks, no filler encouragement beyond the existing "nice work" pattern
  used sparingly.

## Definition of Done

- [ ] Backend returns `startDate` on the plan endpoint; existing + new tests green.
- [ ] `/app` shows the current week's plan for the most recent ready goal, with correct week-math
      across upcoming / active / finished states.
- [ ] `/app/new` hosts the goal form (moved from `/`); all internal links updated.
- [ ] No new dependencies added; styling reuses existing `App.css` classes.
- [ ] Manual walkthrough (all 9 scenarios above) completed against a locally running server.
