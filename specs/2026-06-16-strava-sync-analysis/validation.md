# Phase 2 — Strava Sync + Real Data Analysis: Validation

## Definition of Done

Phase 2 is ready to merge when all checks below pass without manual intervention.

---

## 1. Automated Integration Tests (required)

Run with: `pytest tests/ -v`

| # | Test case | Pass criterion |
|---|---|---|
| 1.1 | `GET /strava/connect` | HTTP 302; `Location` header points to Strava authorize URL with `client_id`, `redirect_uri`, `scope`, `state`; `state` also set as a short-lived signed cookie |
| 1.2 | `GET /strava/callback` with valid `code` + matching `state` (Strava token exchange mocked) | HTTP 302 redirect to `/?connected=1`; `strava_connections` row persisted with tokens |
| 1.3 | `GET /strava/callback` with `state` not matching the cookie | HTTP 400/403; no `strava_connections` row written |
| 1.4 | `GET /strava/status` with no connection stored | HTTP 200; `{"connected": false, "athlete_id": null}` |
| 1.5 | `GET /strava/status` after a connection exists | HTTP 200; `{"connected": true, "athlete_id": <id>}` |
| 1.6 | `POST /strava/disconnect` with a connection stored | HTTP 200; `{"connected": false}`; `strava_connections` row removed |
| 1.7 | `GET /` | HTTP 200; HTML response containing a "Connect with Strava" link to `/strava/connect` |
| 1.8 | `GET /strava/webhook` validation handshake with correct `hub.verify_token` | HTTP 200; body echoes `hub.challenge` |
| 1.9 | `GET /strava/webhook` validation handshake with wrong `hub.verify_token` | HTTP 403 |
| 1.10 | `POST /strava/webhook` with a `create` activity event (activity fetch mocked, matches a planned workout) | HTTP 200 ack; `activity_analyses` row created with non-null adherence fields; `weekly_summaries` row created/updated for that week |
| 1.11 | `POST /strava/webhook` with an activity event for a date with no planned workout | `activity_analyses` row created with `matched_workout_id = null`; excluded from weekly summary |
| 1.12 | `GET /activities?week=4` | HTTP 200; returns only activities matched/unmatched within week 4 |
| 1.13 | `GET /weekly-summary?week_number=4` | HTTP 200; `summary` text non-empty; `sessions` array matches persisted `activity_analyses` |
| 1.14 | `GET /weekly-summary` with no plan/activities yet | HTTP 404 or empty-state response (not 500) |

All DB-touching tests hit a real local Postgres instance — no DB mocking. Outbound Strava HTTP calls are mocked (no live Strava API access required for tests).

---

## 2. Matching Logic Unit Tests (required)

Run with: `pytest tests/test_matching.py -v`

| Check | Criterion |
|---|---|
| Exact date match, distance within tolerance | Returns matched, `mismatch=false` |
| Exact date match, distance far outside tolerance (e.g. 5K logged for a 20K long-run slot) | Returns matched, `mismatch=true` |
| No workout scheduled that date | Returns unmatched |
| Distance exactly at tolerance boundary (±30%) | Inclusive boundary documented and tested on both sides |

---

## 3. Manual Smoke Test (required before merge)

Requires a real Strava developer app + test account. Start the server locally (`uvicorn app.main:app`) and confirm:

- [ ] Visiting `/` shows the connect UI with a "Connect with Strava" button and a "not connected" status — no env file edits or token entry required to reach this point.
- [ ] Clicking "Connect with Strava" redirects to Strava's real OAuth consent screen.
- [ ] Approving the consent screen redirects back through `/strava/callback` and lands on `/` showing "Connected as athlete {id}" — no raw JSON shown to the user at any point in the flow.
- [ ] Reloading `/` after connecting still shows "Connected" (driven by `GET /strava/status`, not just the one-time redirect flag).
- [ ] Clicking "Disconnect" clears the connection and the UI reverts to "not connected" without restarting the server or touching the database manually.
- [ ] Running `scripts/register_strava_webhook.py` successfully creates a Strava webhook subscription (verify via Strava's subscription list API).
- [ ] Logging a real run on Strava triggers the webhook within Strava's normal delivery window, and the activity appears in `GET /activities` shortly after.
- [ ] If that activity's date matches a planned workout, `GET /weekly-summary` reflects it with a sensible adherence assessment.
- [ ] An expired access token (simulate by manually setting `expires_at` in the past) is transparently refreshed on the next sync without user-visible failure.
- [ ] Server logs show no unhandled exceptions during the above.

---

## 4. Merge Blockers

The following will block merge regardless of tests passing:

- Raw SQL in route handlers (all DB access must go through repositories, per Phase 1 convention).
- Strava `client_secret`, API keys, or DB URLs hardcoded anywhere in source (must come from `.env`).
- Missing new env vars in `.env.example`: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_WEBHOOK_VERIFY_TOKEN`, `STRAVA_REDIRECT_URI`.
- Activity analysis calling Claude through anything other than the existing `AIClient` abstraction (`app/ai/client.py` / `app/ai/factory.py`).
- Webhook `POST` handler not returning within Strava's 2-second ack window (must ack before/while doing heavy work, not block on it).
- Raw Strava activity payloads persisted to the database (out of scope per requirements.md Decisions).
- Connect UI requiring the end user to manually enter a token, code, or any `.env` value to complete the connect/disconnect flow.
- New frontend dependency (template engine, JS framework, bundler) added for the connect UI — must stay `HTMLResponse` + vanilla JS per requirements.md.
