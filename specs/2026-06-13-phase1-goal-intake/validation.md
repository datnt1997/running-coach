# Phase 1 — Goal Intake + Static Plan Generation: Validation

## Definition of Done

Phase 1 is ready to merge when all checks below pass without manual intervention.

---

## 1. Automated Integration Tests (required)

Run with: `pytest tests/ -v`

| # | Test case | Pass criterion |
|---|---|---|
| 1.1 | `POST /goal` — valid HM (e.g. sub 1:55, 16 weeks out) | HTTP 200; response matches `PlanResponse` schema; `plan_id` is a valid UUID |
| 1.2 | `POST /goal` — valid FM (e.g. sub 4:30, 20 weeks out) | HTTP 200; `total_weeks` ≥ 12 |
| 1.3 | `POST /goal` — HM target 1:38:00 (too fast) | HTTP 422; `error == "goal_out_of_scope"` |
| 1.4 | `POST /goal` — FM target 3:50:00 (too fast) | HTTP 422; `error == "goal_out_of_scope"` |
| 1.5 | `POST /goal` — race date 6 weeks from today (too soon) | HTTP 422; message references minimum lead time |
| 1.6 | `GET /plan/{plan_id}` after successful POST | HTTP 200; returned plan matches what POST returned |
| 1.7 | `GET /plan/{unknown_uuid}` | HTTP 404 |

All tests hit a real local Postgres instance. No DB mocking allowed.

---

## 2. Plan Quality Checks (required)

Assertions run inside test 1.1 and 1.2:

| Check | Criterion |
|---|---|
| Phase coverage | Plan contains all four phases: `base`, `build`, `peak`, `taper` |
| Week count | `total_weeks` matches `len(weeks)` in response |
| Workout fields | Every workout has non-null `day`, `type`, `distance_km`, `pace_zone` |
| Rest days respected | Number of non-rest workout days per week ≤ `days_per_week` submitted |
| Mileage progression | No single week increases total distance > 10% vs. previous week (checked programmatically) |
| Taper present | Last 2 weeks have lower total distance than peak week |

---

## 3. Goal Validation Unit Tests (required)

Run with: `pytest tests/test_validation.py -v`

| Check | Criterion |
|---|---|
| HM at exactly 1:44:00 | Accepted (boundary is exclusive — sub 1:44 is out of scope) |
| HM at 1:44:01 | Accepted |
| HM at 1:43:59 | Rejected |
| FM at exactly 3:59:00 | Accepted |
| FM at 3:58:59 | Rejected |
| Race date exactly 10 weeks out | Accepted |
| Race date 9 weeks + 6 days | Rejected |

---

## 4. Manual Smoke Test (required before merge)

Start the server locally (`uvicorn app.main:app`) and confirm:

- [ ] `POST /goal` with a realistic HM goal returns a human-readable `summary` that mentions the target time and race distance.
- [ ] The plan has sensible week structure — easy runs early, long runs on weekends, taper visible in final weeks.
- [ ] `GET /plan/{plan_id}` returns the same plan without re-invoking the AI client.
- [ ] Server logs show no unhandled exceptions.

---

## 5. Merge Blockers

The following will block merge regardless of tests passing:

- Raw SQL in route handlers (all DB access must go through repositories).
- API keys or DB URLs hardcoded anywhere in source (must come from `.env`).
- Missing `.env.example` with all required variable names documented.
- `POST /goal` calling Claude more than once per request.
