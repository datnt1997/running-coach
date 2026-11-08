# Plan: VDOT-based level assessment

Small vertical slices; run `pytest` (and `npm run` check scripts for the frontend) after each. Research tasks come first because they decide later work.

## Research (no code)

- [ ] **R1. Age adjustment**: read Tables 5.7 and 5.8 (about pp. 150–153) and write the age → level adjustment into `research.md` in this folder (numbers only, with page refs; no pasted tables).
  - Verify: hand-check two examples from the book's own text (the 58-year-old and 10-year-old examples near Table 5.7).
- [ ] **R2. Strava best efforts** (docs done; one item open): `best_efforts` is returned only by the detailed activity (`GET /activities/{id}`), per activity, for runs; our existing `activity:read_all` scope is enough; read limits are 100 requests per 15 min and 1,000 per day (details in `research.md`).
  - Open: one redacted sample payload to confirm the effort names and distances (the docs do not list them). Needs a real run fetched with the user's token, so ask the user to run one `curl` and paste the `best_efforts` array.
- [x] **R2b. Recency window for "current" fitness**: done; findings in `research.md`. Decisions:
  - Book gives no race-recency period. Closest basis: p. 44 (a runner who trained at the same intensity for 4–6 weeks can raise intensity a little). **Window = 6 weeks**, a tunable setting (`STRAVA_WINDOW_WEEKS`), documented as inferred, not a book rule. No official V.O2 or academic source gives a number; only one non-authoritative site says 4–8 weeks.
  - Effort distance: **10K or longer only**, longer and more recent is better (pp. 336 and 321).
  - After a break (6 or more days since the last run), multiply the chosen VDOT by the Table 15.1 factor (p. 382). It does not reduce an old effort when the user kept running.
  - Highest VDOT in the window wins; race-tagged runs (`workout_type` 1) are flagged as `source: race`. Qualify only with at least 3 runs and 15 km per week over the last 4 weeks; otherwise fall back to the question flow.
  - The estimate is a suggestion: show the effort's date and distance, and the user confirms or overrides it.
  - Verified by three hand-built histories (steady runner, returning after a break, one old PR with low volume); they become the task 6 fixtures.
  - Still unknown for the break rule: whether breaks of 72 days or more should return an estimate or fall back to the questions.
- [ ] **R3. Level → label mapping**: decide how the book's levels 1–10 map to `beginner / intermediate / advanced`. Propose a mapping and confirm with the user.

## Tasks

- [ ] **1. VDOT module**: add `app/vdot.py` with `vdot_from_race(distance_m, seconds)`, `race_time_for_vdot(vdot, distance_m)`, `level_for(vdot, sex, age)`, `break_factor(days_off, cross_trained)` (Table 15.1, p. 382; see `research.md`).
  - Files: `app/vdot.py`, `tests/test_vdot.py`
  - Verify: tests against rows of Table 5.1 (5K–FM, tolerance in requirements 3 and 4) and Table 5.6 thresholds for each sex; level examples from R1.
- [ ] **2. Migration + models**: `app/db/migrations/005_goal_vdot.sql` adds nullable `user_goals.vdot`; `GoalRequest.vdot: float | None`; repository saves it; `tests/conftest.py` applies the migration.
  - Files: migration, `app/models/goal.py`, `app/db/repositories.py`, `tests/conftest.py`
  - Verify: goal endpoint test with and without `vdot`; old rows read back with `vdot = None`.
- [ ] **3. Plan prompt**: include VDOT when set (training paces and load calibration), unchanged when null.
  - Files: `app/agent/prompt.py`, `tests/test_goal_endpoint.py`
  - Verify: prompt test for both cases.
- [ ] **4. Chat collects sex and age first; code computes the result**: change `app/api/fitness_chat.py` so the model gathers signals (sex, age, race time + distance, weekly km, longest run) and Python computes VDOT, level and predictions; response carries them.
  - Files: `app/api/fitness_chat.py`, `tests/test_fitness_chat.py`
  - Verify: fake-client tests cover sex/age first, a complete assessment, and a missing-signal turn. Parser changes ship with their tests in the same commit.
- [ ] **5. Frontend**: show VDOT, level and predicted times; send `vdot` with the goal; add sex/age wording to `vi.js` and run `frontend/scripts/check-i18n.mjs`.
  - Files: `frontend/src/components/FitnessChat.jsx`, `frontend/src/pages/GoalForm.jsx`, `frontend/src/i18n/vi.js`, `frontend/src/lib/vdot.js` (parity test or shared fixtures with `app/vdot.py`)
  - Verify: `npm run` build and i18n check; manual run in the browser.
- [ ] **6. Strava estimate** (blocked on the R2 sample payload and task 1's `break_factor`): implement the R2b rule.
  - Extend `StravaClient` (`app/strava/client.py`) with a list-activities call (`after`, `per_page` 100, paging) and parse `best_efforts`, `sport_type` and `workout_type` from detail calls; fetch detail only for runs of 10 km or more and race-tagged runs.
  - Pure function: runs and efforts in, `{vdot, effort_date, effort_distance, source, window_weeks, days_since_last_run, break_adjustment}` or `insufficient_data` out. Keep it free of I/O so tests need no network.
  - Endpoint or chat step returns the estimate as a suggestion for the user to confirm or override.
  - Files: `app/strava/*`, `app/api/*`, tests with `FakeStravaClient`
  - Verify: fixtures from the three R2b histories, plus no Strava connection; break factor examples from the book (42 days gives 0.889 and 0.944); a test that an effort older than the window is ignored.
- [ ] **7. Docs**: update `CLAUDE.md` (new module, migration list, flow) and this folder's `validation.md`.

## Risks

- The model may still ask questions out of order or skip sex/age. Mitigation: code, not the model, decides when the signal set is complete; tests with the fake client.
- Stale efforts overstate (or understate) current fitness. Mitigation: 6-week window, 10K-or-longer efforts, minimum recent volume, break factor from R2b; show the effort date and let the user override.
- The 6-week window is inferred, not a book rule, and will send many users to the question flow. Mitigation: keep it a setting, say so in the spec, and revisit with real data after task 6.
- Strava read limits (100 per 15 min) can be hit by the detail calls. Mitigation: only runs of 10 km or more and race-tagged runs; cache the result per user.
- Training runs understate fitness versus races. Mitigation: use best efforts only; fall back to the question flow when data is thin (task 6).
- Frontend and backend VDOT code can drift. Mitigation: shared test fixtures from Table 5.1 points.
- The book's tables are copyrighted. Mitigation: store only the small thresholds and coefficients we need, with page refs; never commit the PDF.
