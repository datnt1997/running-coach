from fastapi import APIRouter, Depends
from psycopg import AsyncConnection

from app.db.connection import get_db
from app.db.repositories import ActivityAnalysisRepository, PlanRepository

router = APIRouter()


@router.get("/activities")
async def list_activities(
    week: int | None = None,
    db: AsyncConnection = Depends(get_db),
) -> dict:
    plan_id = await PlanRepository(db).get_latest_plan_id()
    if plan_id is None:
        return {"activities": []}

    rows = await ActivityAnalysisRepository(db).list_for_week(plan_id, week)

    activities = []
    for row in rows:
        if row.get("pace_adherence") is not None:
            status = "complete"
        elif row["matched_workout_id"] is not None:
            status = "pending"
        else:
            status = "unmatched"
        activities.append(
            {
                "stravaActivityId": row["strava_activity_id"],
                "date": row["activity_date"].isoformat(),
                "distanceKm": float(row["distance_km"]),
                "matchedWorkoutId": (
                    str(row["matched_workout_id"]) if row["matched_workout_id"] else None
                ),
                "mismatch": row["mismatch"],
                "analysisStatus": status,
            }
        )
    return {"activities": activities}
