from uuid import UUID

from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from app.auth import require_runner
from app.db.connection import get_db
from app.db.repositories import ProfileRepository
from app.hr_zones import missing_for_zones, profile_zones
from app.models.profile import ProfileRequest

router = APIRouter()

_CAMEL = {"max_hr": "maxHr", "lactate_threshold_hr": "lactateThresholdHr"}


def profile_response(row: dict | None) -> dict:
    row = row or {}
    return {
        "maxHr": row.get("max_hr"),
        "lactateThresholdHr": row.get("lactate_threshold_hr"),
        "restingHr": row.get("resting_hr"),
        "cadence": row.get("cadence"),
        "zones": profile_zones(row),
        # What the zones still need; the UI turns this into a message.
        "missing": [_CAMEL[k] for k in missing_for_zones(row)],
    }


@router.get("/profile")
async def get_profile(
    db: AsyncConnection = Depends(get_db), runner_id: UUID = Depends(require_runner)
) -> dict:
    return profile_response(await ProfileRepository(db, runner_id).get())


@router.put("/profile")
async def put_profile(
    profile: ProfileRequest,
    db: AsyncConnection = Depends(get_db),
    runner_id: UUID = Depends(require_runner),
) -> dict:
    repo = ProfileRepository(db, runner_id)
    await repo.save(profile)
    await db.commit()
    return profile_response(await repo.get())
