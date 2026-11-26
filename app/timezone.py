"""The runner's "today". The server runs on UTC; the browser sends its IANA timezone."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request

TZ_HEADER = "X-Timezone"


def today_in(tz_name: str | None, now: datetime | None = None) -> date:
    """Today's date in this IANA timezone; UTC when it is missing or unknown."""
    now = now or datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        tz = timezone.utc
    return now.astimezone(tz).date()


def runner_today(request: Request) -> date:
    """FastAPI dependency: today for the runner making this request (header `X-Timezone`)."""
    return today_in(request.headers.get(TZ_HEADER))
