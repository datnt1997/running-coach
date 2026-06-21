# Phase 2 — Strava Sync + Real Data Analysis: Implementation Plan

## Group 1 — Config & Migration

1.1 Add `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_WEBHOOK_VERIFY_TOKEN`, `STRAVA_REDIRECT_URI` to `.env` and `app/config.py` (validated in `validate_config()`)
1.2 Write `app/db/migrations/002_strava.sql` — `strava_connections`, `activity_analyses`, `weekly_summaries` tables (schema from requirements.md)

---

## Group 2 — Strava Client

2.1 `app/strava/client.py` — `StravaClient` wrapping Strava's REST API: `exchange_code(code) -> TokenSet`, `refresh_token(refresh_token) -> TokenSet`, `get_activity(activity_id, access_token) -> ActivityDetail`
2.2 `app/strava/models.py` — `TokenSet`, `ActivityDetail` Pydantic models for Strava API responses (only the fields the app uses: id, start_date_local, distance, average_heartrate, moving_time, type)
2.3 Token refresh wrapper: a helper that loads the stored connection, refreshes if `expires_at` has passed, persists the new token set, and returns a valid access token for use by callers

---

## Group 3 — Database Layer

3.1 `app/db/repositories.py` — add `StravaConnectionRepository` (`upsert`, `get`, `update_tokens`)
3.2 `app/db/repositories.py` — add `ActivityAnalysisRepository` (`insert`, `get_by_strava_id`, `list_for_week`)
3.3 `app/db/repositories.py` — add `WeeklySummaryRepository` (`upsert`, `get_by_week`)

---

## Group 4 — OAuth Endpoints

4.1 `app/api/strava.py` — `GET /strava/connect`: build Strava authorize URL with `client_id`, `redirect_uri`, `scope=activity:read_all`, CSRF `state` (state stored in a short-lived signed cookie, not query-passed back and forth); 302 redirect
4.2 `app/api/strava.py` — `GET /strava/callback`: validate `state` against the cookie, exchange `code` via `StravaClient.exchange_code`, persist via `StravaConnectionRepository.upsert`, then redirect (302) to the UI connect page (`/`) with a `connected=1` flag so the browser flow never needs the user to read/copy a JSON response
4.3 `app/api/strava.py` — `GET /strava/status`: returns `{"connected": bool, "athlete_id": int | null}` for the currently stored connection — used by the UI to render its state without polling Strava
4.4 `app/api/strava.py` — `POST /strava/disconnect`: deletes the stored `strava_connections` row (local disconnect only; does not revoke the Strava-side grant)

---

## Group 5 — Strava Connect UI

No new frontend dependency: server-rendered single page via `fastapi.responses.HTMLResponse`, vanilla JS `fetch` for status/disconnect, no template engine or JS framework added.

5.1 `app/api/ui.py` — `GET /`: returns a single static HTML page with a "Connect with Strava" button (links to `/strava/connect`), a connection status area, and a "Disconnect" button — all driven by calling `GET /strava/status` and `POST /strava/disconnect` from inline JS
5.2 Page reads the `connected=1` redirect flag (Group 4.2) to show an immediate "Connected as athlete {id}" confirmation after the OAuth round-trip, then falls back to `GET /strava/status` on normal page loads
5.3 `app/main.py` — mount the UI route; confirm `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` stay developer-level app-registration config (set once in `.env` by whoever runs the server) — the end user authenticating through the browser never sees or enters those values, only their own Strava login on Strava's own consent screen
5.4 No manual token/code entry anywhere in the UI — the entire connect/disconnect lifecycle is click-driven

---

## Group 6 — Matching Logic

6.1 `app/agent/matching.py` — `match_activity_to_workout(activity: ActivityDetail, candidate_workouts: list[WorkoutSession]) -> MatchResult` implementing date-based lookup + type/distance plausibility check (±30% tolerance constant)
6.2 `MatchResult` covers three outcomes: matched (clean), matched (`mismatch=true`), unmatched
6.3 Unit tests for all three outcomes plus boundary tolerance cases

---

## Group 7 — Analysis via AIClient

7.1 `app/ai/tools.py` — add `analyze_activity` tool definition (structured output: `pace_adherence`, `hr_adherence`, `load_adherence`, short rationale text)
7.2 `app/agent/prompt.py` — add prompt builder for activity analysis: planned workout + actual activity data + the three core signals (pace zone adherence, HR vs. prescription, load = volume × intensity)
7.3 `app/agent/analyzer.py` — `analyze_activity(planned: WorkoutSession, actual: ActivityDetail) -> ActivityAnalysis` calling `get_ai_client().generate(...)`, parsed via Pydantic; raises `AnalysisGenerationError` on malformed output
7.4 `app/agent/analyzer.py` — `build_weekly_summary(plan_id, week_number) -> str` calls Claude once per week to roll up that week's `activity_analyses` rows into a human-readable summary (e.g. "You ran your tempo 12s/km too fast...")

---

## Group 8 — Webhook Endpoint

8.1 `app/api/strava.py` — `GET /strava/webhook` (Strava subscription validation): echo `hub.challenge` if `hub.verify_token` matches `STRAVA_WEBHOOK_VERIFY_TOKEN`, else 403
8.2 `app/api/strava.py` — `POST /strava/webhook`: parse event body; on `aspect_type == "create"` and `object_type == "activity"`, ack 200 immediately, then: refresh token if needed → fetch activity detail → match → analyze → persist `activity_analyses` row → upsert `weekly_summaries` for that activity's week
8.3 One-time webhook subscription setup script (`scripts/register_strava_webhook.py`) that calls Strava's subscription-create endpoint with `STRAVA_REDIRECT_URI`-derived callback URL and verify token — run manually, not part of app startup

---

## Group 9 — Read Endpoints

9.1 `app/api/activities.py` — `GET /activities` with optional `week` query param, backed by `ActivityAnalysisRepository.list_for_week`
9.2 `app/api/plans.py` (or new `app/api/summaries.py`) — `GET /weekly-summary` with optional `week_number`, backed by `WeeklySummaryRepository.get_by_week`; defaults to the active plan's current week if omitted
9.3 `app/main.py` — wire new routers (`strava`, `ui`, `activities`, `summaries`)

---

## Group 10 — Integration Tests

10.1 `tests/test_strava_oauth.py` — `GET /strava/connect` redirects with correct query params; `GET /strava/callback` persists a connection and redirects to `/` with `connected=1` (mock `StravaClient.exchange_code` only — no live Strava calls in tests)
10.2 `tests/test_strava_status.py` — `GET /strava/status` reflects connected/disconnected state; `POST /strava/disconnect` clears the stored connection
10.3 `tests/test_strava_webhook.py` — webhook GET validation handshake; webhook POST with a mocked activity fetch produces an `activity_analyses` row and updates `weekly_summaries`
10.4 `tests/test_matching.py` — unit tests for `match_activity_to_workout` (clean match, mismatch, unmatched, tolerance boundaries)
10.5 `tests/test_activities_endpoint.py` and `tests/test_weekly_summary_endpoint.py` — `GET /activities` and `GET /weekly-summary` against real local Postgres, seeded with a plan + analyses
10.6 Tests hit real local Postgres for DB-touching assertions (no DB mocking); only the outbound Strava HTTP calls are mocked, consistent with Phase 1's "no mocks on DB" convention
10.7 Manual-only: `GET /` connect page click-through (button → Strava consent → redirect back → status shows "Connected") — not automatable without a live Strava test account, covered in validation.md's manual smoke test instead
