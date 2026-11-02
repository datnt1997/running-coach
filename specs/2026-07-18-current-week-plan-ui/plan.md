# Implementation Plan — Current-Week Plan UI

## 1. Backend: expose `startDate`

1.1. `app/models/plan.py` — add `start_date: date` to `PlanResponse` (alias `startDate` via
     existing `to_camel` config; import `date` from `datetime`, already imported at module top).

1.2. `app/api/goals.py: _build_plan_response` — accept `plan["start_date"]` and pass it into
     `PlanResponse(...)`. `plan` here is the dict returned by
     `PlanRepository.get_plan_by_goal_id`, which already `SELECT`s `start_date`
     (`app/db/repositories.py:201`) — no query change needed.

1.3. Confirm `GET /goal/{goal_id}/plan` response now includes `"startDate": "YYYY-MM-DD"` when
     `status == "ready"`.

## 2. Frontend: week-math utility

2.1. Add `frontend/src/lib/weeks.js` with a pure function:
     `currentWeekNumber(startDate, totalWeeks, today = new Date())` →
     returns `{ weekNumber, status }` where `status` is one of `'upcoming'` (today < startDate),
     `'active'` (within plan range), or `'finished'` (today past totalWeeks * 7 days from start).
     `weekNumber` clamped to `[1, totalWeeks]`.

2.2. Handle date parsing carefully — `startDate` arrives as `YYYY-MM-DD`; compare using local
     calendar days (not UTC timestamps) to avoid off-by-one at day boundaries, consistent with how
     `raceDate` is already handled as a plain string elsewhere in the app.

## 3. Frontend: Dashboard page

3.1. Add `frontend/src/pages/Dashboard.jsx`:
     - On mount, `fetch('/goals')`, pick the most recent goal with `planStatus === 'ready'`
       (fallback: most recent `generating` goal if none ready; else empty state).
     - If a ready goal is found, `fetch('/goal/{goalId}/plan')` for full plan detail (reuses the
       same endpoint `PlanView.jsx` already polls).
     - Compute `currentWeekNumber` via the `weeks.js` utility.
     - Render a "This Week" card: week number, phase badge, workout table (same columns as
       `PlanView.jsx`: Day / Type / Distance / Zone / Notes).
     - Below the card, a compact link-out: "Full plan →" to `/goals/:goalId` (existing `PlanView`).

3.2. Empty/edge states on `Dashboard.jsx`:
     - No goals at all → "No training plan yet." + CTA button to `/new`.
     - Most recent goal still `generating` → same spinner treatment as `PlanView.jsx`.
     - Most recent goal `failed` → error message + link to `/new`.
     - `status === 'upcoming'` (plan starts in the future) → show week 1 with a banner "Starts in
       N days".
     - `status === 'finished'` (past last week) → show final week with a banner "Race day has
       passed — nice work" (adjust copy to match existing terse tone).

## 4. Routing & navigation

4.1. `frontend/src/App.jsx`:
     - Change `<Route path="/" element={<GoalForm />} />` → add
       `<Route path="/" element={<Dashboard />} />` and
       `<Route path="/new" element={<GoalForm />} />`.
     - Update nav: `NavLink to="/"` label becomes "This Week" (or "Dashboard"); add
       `NavLink to="/new"` labeled "New Goal"; keep `NavLink to="/history"`.

4.2. `frontend/src/pages/GoalForm.jsx` — check for any hardcoded `to="/"` links assuming it *is*
     home (e.g. a post-submit redirect target) and update if any point at the old root meaning.

4.3. `frontend/src/pages/GoalHistory.jsx:67` — `<Link to="/">` "+ New Goal" button now points at
     the dashboard, not the form; update to `to="/new"`.

## 5. Styling

5.1. Reuse existing `App.css` classes (`badge`, `phase-*`, table styles) for the "This Week" card
     — no new stylesheet. Add only the minimal new classes needed for the banner/empty states,
     following existing naming (`api-error`, `hint`, etc.).

## 6. Tests

6.1. `tests/test_goal_endpoint.py` — extend existing plan-retrieval assertions (e.g. near line 22,
     the shared assertion helper, and `test_valid_half_marathon` / `test_valid_full_marathon`) to
     assert `"startDate" in plan` and that it parses as a valid ISO date.

6.2. No frontend automated tests exist in this repo (no test runner configured in
     `frontend/package.json`) — frontend changes are validated manually per `validation.md`, not
     with new test infra.
