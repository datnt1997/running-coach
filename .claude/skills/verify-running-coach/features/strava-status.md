# Strava connect page

The plain HTML page at `/` shows whether a Strava athlete is connected and offers Connect or Disconnect.

## Sub-features

- `strava-off` shows `Not connected to Strava` and a `Connect with Strava` button.
- `strava-on` shows `Connected as athlete <id>` and `Disconnect`.

## How to get to it (user POV)

- Open `http://127.0.0.1:8010/`.

## Driving it with Claude in Chrome + psql

Preconditions: baseline.

- **Not connected.** Open `/`; text `Not connected to Strava`. `curl -s $BASE_URL/strava/status` returns `{"connected":false...}`.
- **Connected.** Insert a row: `psql "$VERIFY_DATABASE_URL" -c "insert into strava_connections(strava_athlete_id,access_token,refresh_token,expires_at) values (42,'x','x',now()+interval '1 day')"`, reload; `Connected as athlete 42`. Click `Disconnect`; the row is deleted.

## Gotchas

- `Connect with Strava` redirects to real Strava; do not click it. The OAuth flow is not verifiable here.
- Not yet run in this skill's proof.
