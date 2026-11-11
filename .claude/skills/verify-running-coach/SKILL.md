---
name: verify-running-coach
description: Launch and drive the Running Coach web app (FastAPI + React SPA at /app, Vietnamese UI) against a disposable Postgres and a faked AI client, to prove a change works the way a user sees it. Use after changing goals, plans, fitness chat/VDOT, dashboard, history, or Strava status code.
---

# Verify Running Coach

Surface: the React SPA at `http://127.0.0.1:8010/app` (UI text is Vietnamese by default, `APP_LANGUAGE=vi`) plus the JSON API behind it. Also `GET /` (Strava connect page, plain HTML). Strava OAuth/webhooks need real Strava and are out of scope here.

Everything runs isolated from the dev stack (dev DB :5433, dev server :8000, test DB :5434): Postgres container `running-coach-verify-db` on :5441 (tmpfs, empty each run) and the app on :8010. Only the `AIClient` is faked (`scripts/verify_app.py`), so no Anthropic cost and plans are deterministic: 12 weeks, summary `VERIFY-FAKE-PLAN 12 weeks`, workouts Mon/Wed/Sat with notes `VERIFY ...`. The fake chat asks one race-time question, then returns signals (male, 30, 10K 52:00, 40 km/week, 18 km longest). Real prompt quality is NOT verified here.

Scripts are in `.claude/skills/verify-running-coach/scripts/`; run from the repo root.

## Launch
`.claude/skills/verify-running-coach/scripts/launch.sh`
Starts Docker Postgres, applies all `app/db/migrations/*.sql`, rebuilds `frontend/dist` if sources are newer, starts uvicorn. Prints `ready: ...` only when `/health` answers and `/app` serves the SPA. Needs the Docker daemon (`open -a Docker`), `psql`, `npm`, `.venv`. It refuses to run if the container or port 8010 already exists; run `cleanup.sh` first, never reuse an instance you did not start. Frontend code changes need a relaunch (it serves the built `dist`, not Vite).

## Doctor
`.claude/skills/verify-running-coach/scripts/doctor.sh` is read-only and exits non-zero on any FAIL: container up, schema current, pid alive and owning :8010, `/health`, SPA, and that the server runs `verify_app` (fake AI). Run it first whenever anything looks off.

## Drive
Harness: Claude in Chrome (`mcp__claude-in-chrome__*`, open a new tab; load tools with one ToolSearch call) for the UI, `curl` for the API, `psql "$VERIFY_DATABASE_URL"` (from `scripts/env.sh`) for side effects. Use `read_page` with `filter: interactive` and drive by refs, accessible names, and `placeholder`s, never coordinates. Routes: `/app` (this week), `/app/new`, `/app/goals/<goalId>`, `/app/history`. The feature recipes are in `features/README.md`; start there.

Avoid `window.confirm`: the history Delete button opens a native dialog that blocks the browser tool. Delete through `DELETE /goal/<id>` or override `window.confirm = () => true` with the JS tool first.

## Evidence
Write proofs to `$EVIDENCE/<feature-id>/` (default `$TMPDIR/running-coach-verify/evidence`, printed by launch.sh). Standards:
- Drive the real user path (the form, the chat, the nav links), not the API, when the feature is UI. Use the API/DB only for the second view.
- Capture the action and the resulting state: a screenshot of the final page (save_to_disk, then copy into the evidence dir) plus `psql` output proving rows were written (goal `plan_status = ready`, workout count).
- Fake-AI values (`VERIFY-FAKE-PLAN`, `VERIFY easy`) on screen prove the request went through the real route, DB, and API path.
- Report anything unreachable with the attempted step; never claim a different path verified it.

## Cleanup
`.claude/skills/verify-running-coach/scripts/cleanup.sh` kills only the pid it recorded and removes only `running-coach-verify-db`. Evidence is preserved. Close any browser tabs you opened.
