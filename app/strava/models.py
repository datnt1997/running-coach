from pydantic import BaseModel


class TokenSet(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp
    athlete_id: int | None = None  # present on code exchange, absent on token refresh


class ActivityDetail(BaseModel):
    id: int
    start_date_local: str   # e.g. "2026-06-18T07:30:00Z"
    distance: float         # meters
    moving_time: int        # seconds
    average_heartrate: float | None = None
    type: str               # "Run", "Ride", etc.
