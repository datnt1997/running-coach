# Phase 2 — Strava Sync + Real Data Analysis: Requirements

## Scope

Connect a single user's Strava account, receive new activities in near-real-time via a Strava webhook, and analyze each activity against the planned workout for that day (pace, heart rate, load). Surface a stored weekly summary comparing real vs. prescribed performance. The user authenticates entirely through a minimal browser UI — clicking "Connect with Strava" and logging into Strava's own consent screen — with no manual `.env` editing, token pasting, or API client required for the connect flow itself.

## In Scope

- `GET /` — minimal connect UI: a "Connect with Strava" button, live connection status, and a "Disconnect" button. Server-rendered HTML + vanilla JS, no new frontend framework/dependency.
- `GET /strava/connect` — start Strava OAuth 2.0 authorization redirect.
- `GET /strava/callback` — OAuth callback; exchanges code for access/refresh tokens, persists them, redirects back into the UI.
- `GET /strava/status` — connection status (`connected`, `athlete_id`) for the UI to render without polling Strava directly.
- `POST /strava/disconnect` — removes the locally stored connection (UI-driven, no env/file edits).
- Strava webhook subscription setup (one-time, at startup or via a setup script) and `POST /strava/webhook` callback endpoint that Strava calls on new activity events.
- `GET /activities` — list synced activities with their matched workout and analysis status.
- `GET /weekly-summary` — return the stored weekly summary (real vs. prescribed: pace, HR, load) for the current or a given week.
- Activity → planned workout matching: same calendar date, with a workout-type/distance plausibility check (e.g. a 5 km easy run will not match a 20 km long-run slot). Mismatches are flagged rather than silently matched.
- Claude analyzes each matched activity against its planned workout using three signals: pace (zone adherence), heart rate (effort vs. prescription), and load (volume × intensity). Output is a structured per-activity analysis plus a rolled-up weekly summary.
- Token refresh handling: expired Strava access tokens are refreshed transparently using the stored refresh token before any Strava API call.

## Out of Scope (Phase 2)

- Adaptive re-planning / plan modification (Phase 3).
- TSS / ATL / CTL / TSB computation (Phase 3).
- Chat interface (Phase 4).
- Multi-user support, auth beyond the single Strava-connected account.
- Any UI beyond the single connect/status/disconnect page — no plan browsing, activity list, or weekly-summary UI (those stay API-only this phase; full UI is Phase 5 per roadmap).
- Encrypting Strava tokens at rest (deferred; see Decisions).
- Persisting raw Strava activity payloads (deferred; see Decisions).
- Backfilling historical activities before the webhook subscription was created — sync starts from connect time forward.

## Activity → Workout Matching Rules

| Rule | Behavior |
|---|---|
| Same calendar date | Activity's local start date must equal a `workout_sessions.day_of_week` slot's actual calendar date for that plan week |
| Type/distance plausibility | Activity type (run) + distance within a tolerance band of the planned `workout_type`/`distance_km` (e.g. ±30%, configurable constant) |
| No workout that day | Activity stored as unmatched; excluded from weekly summary; visible in `GET /activities` with `matched_workout_id = null` |
| Plausibility check fails | Activity matched by date but flagged `mismatch=true` (e.g. logged a 5K when a 20K long run was planned) — included in summary with a flag, not silently treated as compliant |

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Sync mechanism | Strava webhook subscription | Roadmap calls for "webhook or polling"; webhook chosen for near-real-time updates without a cron dependency, consistent with Phase 5's eventual automated re-plan trigger |
| Matching strategy | Date + type/distance plausibility | Pure date matching risks silently comparing an unrelated run against the wrong planned session; flagging mismatches preserves signal for the user/coach |
| Raw activity persistence | Not persisted | Only the derived analysis (pace/HR/load vs. plan) is stored; keeps DB lean and avoids duplicating Strava's own activity store. Re-fetch from Strava by `strava_activity_id` if raw detail is ever needed |
| Token storage | Plain Postgres columns, unencrypted | Consistent with Phase 1's single-user, local-trust model; encryption deferred until multi-user or production deployment is in scope |
| Webhook validation | Verify Strava's `hub.verify_token` on subscription handshake; validate `client_secret`-derived signature is not provided by Strava, so rely on the documented subscription validation handshake only | Matches Strava's actual webhook API contract (GET challenge + POST events), avoids inventing unsupported security checks |
| Connect UI | Minimal server-rendered page (HTML + vanilla JS), no template engine or frontend framework | User asked for a click-driven connect flow with no manual env/token input; a single static page is enough and avoids pulling in a new dependency this phase |
| App-level Strava credentials | `STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET` stay developer-set env vars (one-time server setup), never entered by the end user | These are Strava's own app-registration requirement, not per-user secrets — the *end user* only ever clicks a button and logs into Strava's consent screen, which satisfies "no manual info input" for the person using the app |

## API Contract

### `GET /`

Returns the connect UI: an HTML page with a "Connect with Strava" button (links to `/strava/connect`), a status area populated via `GET /strava/status`, and a "Disconnect" button (calls `POST /strava/disconnect`). If loaded with `?connected=1` (see callback below), shows an immediate "Connected as athlete {id}" confirmation instead of waiting on the status fetch.

### `GET /strava/connect`

Redirects (302) to Strava's OAuth authorize URL with `client_id`, `redirect_uri`, `scope=activity:read_all`, and a CSRF `state` param (state stored in a short-lived signed cookie).

### `GET /strava/callback`

**Query params:** `code`, `state`, `scope`

**Behavior:** validates `state` against the cookie, exchanges `code` for tokens via Strava's `/oauth/token`, persists `access_token`, `refresh_token`, `expires_at`, `strava_athlete_id` to `strava_connections`. Redirects (302) to `/?connected=1` — the browser lands back on the connect UI already showing success, with no raw JSON ever shown to the user.

### `GET /strava/status`

**Response (200):**
```json
{ "connected": true, "athlete_id": 123456 }
```
`connected: false, athlete_id: null` when no `strava_connections` row exists.

### `POST /strava/disconnect`

Deletes the stored `strava_connections` row. **Response (200):** `{ "connected": false }`. Local disconnect only — does not revoke the grant on Strava's side.

### `POST /strava/webhook`

**Strava subscription validation (GET):** echoes `hub.challenge` when `hub.verify_token` matches the configured value.

**Event delivery (POST):** body per Strava's webhook event schema (`object_type`, `object_id`, `aspect_type`, `owner_id`). On `aspect_type == "create"` and `object_type == "activity"`, fetch full activity detail from Strava, run matching + analysis, persist results. Always return 200 quickly (Strava requires ack within 2s) — heavy work happens after the response or in-process synchronously if fast enough for v1.

### `GET /activities`

**Query params (optional):** `week` (ISO week or week_number relative to a plan)

**Response (200):**
```json
{
  "activities": [
    {
      "strava_activity_id": 123456789,
      "date": "2026-06-16",
      "distance_km": 8.2,
      "matched_workout_id": "<uuid>",
      "mismatch": false,
      "analysis_status": "complete"
    }
  ]
}
```

### `GET /weekly-summary`

**Query params (optional):** `week_number` (defaults to current week of the active plan)

**Response (200):**
```json
{
  "week_number": 4,
  "phase": "build",
  "summary": "You ran your tempo 12s/km too fast — HR zone 4 vs. prescribed zone 3. Long run load was on target.",
  "sessions": [
    {
      "planned": { "day": "Wed", "type": "tempo", "distance_km": 6.0, "pace_zone": "Z3" },
      "actual": { "distance_km": 6.1, "avg_pace_per_km": "4:42", "avg_hr_zone": "Z4" },
      "pace_adherence": "too_fast",
      "hr_adherence": "above_prescribed",
      "load_adherence": "on_target",
      "mismatch": false
    }
  ]
}
```

## Database Schema Additions

```sql
CREATE TABLE strava_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strava_athlete_id BIGINT NOT NULL UNIQUE,
    access_token    TEXT NOT NULL,
    refresh_token   TEXT NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE activity_analyses (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strava_activity_id  BIGINT NOT NULL UNIQUE,
    matched_workout_id  UUID REFERENCES workout_sessions(id),
    activity_date       DATE NOT NULL,
    distance_km         NUMERIC(5,2) NOT NULL,
    avg_pace_per_km     INTERVAL,
    avg_hr_zone         TEXT,
    pace_adherence      TEXT,           -- 'on_target' | 'too_fast' | 'too_slow'
    hr_adherence        TEXT,           -- 'on_target' | 'above_prescribed' | 'below_prescribed'
    load_adherence      TEXT,           -- 'on_target' | 'overreaching' | 'underloaded'
    mismatch            BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE weekly_summaries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID REFERENCES training_plans(id),
    week_number INT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (plan_id, week_number)
);
```

## Constraints from Tech Stack

- Python 3.12+, FastAPI, Pydantic v2, `psycopg` async (matches Phase 1 `repositories.py` pattern, not `asyncpg`).
- Plan generation already calls Claude via `AIClient` abstraction (`app/ai/client.py`); analysis must reuse the same abstraction and `app/ai/factory.py`, not a new direct SDK call.
- New env vars (add to `.env.example` and `app/config.py`): `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_WEBHOOK_VERIFY_TOKEN`, `STRAVA_REDIRECT_URI`.
- No raw SQL in route handlers — all DB access through repositories, matching Phase 1 convention (`app/db/repositories.py`).
- Connect UI introduces no new dependency: `fastapi.responses.HTMLResponse` + inline vanilla JS only — no Jinja2, no JS framework, no new entry in `pyproject.toml`.
