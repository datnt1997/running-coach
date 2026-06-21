from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from app.db.connection import get_db
from app.db.repositories import ActivityAnalysisRepository, PlanRepository, WeeklySummaryRepository

router = APIRouter()


@router.get("/weekly-summary")
async def get_weekly_summary(
    week_number: int | None = None,
    db: AsyncConnection = Depends(get_db),
) -> dict:
    plan_repo = PlanRepository(db)
    plan_id = await plan_repo.get_latest_plan_id()
    if plan_id is None:
        raise HTTPException(status_code=404, detail="No training plan found")

    if week_number is None:
        plan = await plan_repo.get_plan(plan_id)
        if plan is None or plan.get("start_date") is None:
            raise HTTPException(status_code=404, detail="Plan has no start date")
        elapsed = (date.today() - plan["start_date"]).days
        week_number = max(1, min(elapsed // 7 + 1, plan["total_weeks"]))

    summary_row = await WeeklySummaryRepository(db).get_by_week(plan_id, week_number)
    if summary_row is None:
        raise HTTPException(status_code=404, detail=f"No summary for week {week_number}")

    rows = await ActivityAnalysisRepository(db).list_for_week(plan_id, week_number)

    sessions = []
    for row in rows:
        if row.get("matched_workout_id") is None:
            continue
        avg_pace = row.get("avg_pace_per_km")
        avg_pace_str = None
        if avg_pace is not None:
            total = int(avg_pace.total_seconds())
            mins, secs = divmod(total, 60)
            avg_pace_str = f"{mins}:{secs:02d}"

        sessions.append(
            {
                "planned": {
                    "day": row.get("day_of_week"),
                    "type": row.get("workout_type"),
                    "distanceKm": (
                        float(row["planned_distance_km"])
                        if row.get("planned_distance_km") is not None
                        else None
                    ),
                    "paceZone": row.get("pace_zone"),
                },
                "actual": {
                    "distanceKm": float(row["distance_km"]),
                    "avgPacePerKm": avg_pace_str,
                    "avgHrZone": row.get("avg_hr_zone"),
                },
                "paceAdherence": row.get("pace_adherence"),
                "hrAdherence": row.get("hr_adherence"),
                "loadAdherence": row.get("load_adherence"),
                "mismatch": row["mismatch"],
            }
        )

    return {
        "weekNumber": week_number,
        "phase": rows[0].get("phase") if rows else None,
        "summary": summary_row["summary"],
        "sessions": sessions,
    }
