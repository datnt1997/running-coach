from datetime import datetime, timezone

import httpx

from app.config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REDIRECT_URI
from app.strava.models import ActivityDetail, TokenSet

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


class StravaClient:
    async def exchange_code(self, code: str) -> TokenSet:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": STRAVA_CLIENT_ID,
                    "client_secret": STRAVA_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": STRAVA_REDIRECT_URI,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=data["expires_at"],
                athlete_id=data["athlete"]["id"],
            )

    async def refresh_token(self, refresh_token_value: str) -> TokenSet:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                STRAVA_TOKEN_URL,
                data={
                    "client_id": STRAVA_CLIENT_ID,
                    "client_secret": STRAVA_CLIENT_SECRET,
                    "refresh_token": refresh_token_value,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return TokenSet(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=data["expires_at"],
            )

    async def get_activity(self, activity_id: int, access_token: str) -> ActivityDetail:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{STRAVA_API_BASE}/activities/{activity_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return ActivityDetail(
                id=data["id"],
                start_date_local=data["start_date_local"],
                distance=data["distance"],
                moving_time=data["moving_time"],
                average_heartrate=data.get("average_heartrate"),
                type=data["type"],
            )


async def get_valid_access_token(conn, strava_client: "StravaClient | None" = None) -> str:
    """Load the stored connection, refresh if expired, return a valid access token."""
    from app.db.repositories import StravaConnectionRepository

    if strava_client is None:
        strava_client = StravaClient()

    repo = StravaConnectionRepository(conn)
    connection = await repo.get()
    if connection is None:
        raise RuntimeError("No Strava connection found")

    now = datetime.now(timezone.utc)
    if connection["expires_at"] <= now:
        new_tokens = await strava_client.refresh_token(connection["refresh_token"])
        await repo.update_tokens(
            access_token=new_tokens.access_token,
            refresh_token=new_tokens.refresh_token,
            expires_at=datetime.fromtimestamp(new_tokens.expires_at, tz=timezone.utc),
        )
        return new_tokens.access_token

    return connection["access_token"]
