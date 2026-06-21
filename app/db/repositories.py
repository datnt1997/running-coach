from datetime import date, datetime, timedelta
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.models.goal import GoalRequest
from app.models.plan import PlannedWorkout


def _parse_target_time(target_time: str) -> timedelta:
    parts = [int(p) for p in target_time.split(":")]
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours, minutes, seconds = 0, parts[0], parts[1]
    else:
        raise ValueError(f"Invalid target_time format: {target_time!r}")
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


class GoalRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def insert(self, goal: GoalRequest) -> UUID:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_goals
                    (distance, target_time, race_date, fitness_level,
                     days_per_week, injury_history)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    goal.distance,
                    _parse_target_time(goal.target_time),
                    goal.race_date,
                    goal.fitness_level,
                    goal.days_per_week,
                    goal.injury_history,
                ),
            )
            row = await cur.fetchone()
            return row[0]

    async def get(self, goal_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM user_goals WHERE id = %s",
                (goal_id,),
            )
            return await cur.fetchone()

    async def update_status(self, goal_id: UUID, status: str) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE user_goals SET plan_status = %s WHERE id = %s",
                (status, goal_id),
            )

    async def list_all(self) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, distance, target_time, race_date, fitness_level,
                       days_per_week, plan_status, created_at
                FROM user_goals
                ORDER BY created_at DESC
                """
            )
            return await cur.fetchall()

    async def delete(self, goal_id: UUID) -> bool:
        async with self.conn.cursor() as cur:
            # Null out FK references from activity_analyses to workouts being deleted
            await cur.execute(
                """
                UPDATE activity_analyses SET matched_workout_id = NULL
                WHERE matched_workout_id IN (
                    SELECT ws.id FROM workout_sessions ws
                    JOIN training_plans tp ON ws.plan_id = tp.id
                    WHERE tp.goal_id = %s
                )
                """,
                (goal_id,),
            )
            await cur.execute(
                "DELETE FROM weekly_summaries WHERE plan_id IN (SELECT id FROM training_plans WHERE goal_id = %s)",
                (goal_id,),
            )
            await cur.execute(
                "DELETE FROM workout_sessions WHERE plan_id IN (SELECT id FROM training_plans WHERE goal_id = %s)",
                (goal_id,),
            )
            await cur.execute("DELETE FROM training_plans WHERE goal_id = %s", (goal_id,))
            await cur.execute("DELETE FROM user_goals WHERE id = %s RETURNING id", (goal_id,))
            row = await cur.fetchone()
            return row is not None


class PlanRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def insert_plan(
        self,
        goal_id: UUID,
        total_weeks: int,
        summary: str,
        start_date: date | None = None,
    ) -> UUID:
        if start_date is None:
            start_date = date.today()
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO training_plans (goal_id, total_weeks, summary, start_date)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (goal_id, total_weeks, summary, start_date),
            )
            row = await cur.fetchone()
            return row[0]

    async def insert_workout(
        self,
        plan_id: UUID,
        week_number: int,
        phase: str,
        day: str,
        workout_type: str,
        distance_km: float | None,
        pace_zone: str | None,
        notes: str | None,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO workout_sessions
                    (plan_id, week_number, phase, day_of_week, workout_type,
                     distance_km, pace_zone, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    plan_id,
                    week_number,
                    phase,
                    day,
                    workout_type,
                    distance_km,
                    pace_zone,
                    notes,
                ),
            )

    async def get_plan(self, plan_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, goal_id, total_weeks, summary, start_date
                FROM training_plans
                WHERE id = %s
                """,
                (plan_id,),
            )
            plan = await cur.fetchone()
            if plan is None:
                return None

            await cur.execute(
                """
                SELECT week_number, phase, day_of_week, workout_type,
                       distance_km, pace_zone, notes
                FROM workout_sessions
                WHERE plan_id = %s
                ORDER BY week_number,
                    CASE day_of_week
                        WHEN 'Mon' THEN 1
                        WHEN 'Tue' THEN 2
                        WHEN 'Wed' THEN 3
                        WHEN 'Thu' THEN 4
                        WHEN 'Fri' THEN 5
                        WHEN 'Sat' THEN 6
                        WHEN 'Sun' THEN 7
                        ELSE 8
                    END
                """,
                (plan_id,),
            )
            workout_rows = await cur.fetchall()

        plan["workouts"] = workout_rows
        return plan

    async def get_plan_by_goal_id(self, goal_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, goal_id, total_weeks, summary, start_date FROM training_plans WHERE goal_id = %s",
                (goal_id,),
            )
            plan = await cur.fetchone()
            if plan is None:
                return None
            await cur.execute(
                """
                SELECT week_number, phase, day_of_week, workout_type,
                       distance_km, pace_zone, notes
                FROM workout_sessions
                WHERE plan_id = %s
                ORDER BY week_number,
                    CASE day_of_week
                        WHEN 'Mon' THEN 1 WHEN 'Tue' THEN 2 WHEN 'Wed' THEN 3
                        WHEN 'Thu' THEN 4 WHEN 'Fri' THEN 5 WHEN 'Sat' THEN 6
                        WHEN 'Sun' THEN 7 ELSE 8
                    END
                """,
                (plan["id"],),
            )
            plan["workouts"] = await cur.fetchall()
        return plan

    async def get_latest_plan_id(self) -> UUID | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM training_plans ORDER BY created_at DESC LIMIT 1"
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def get_workouts_for_date(
        self, plan_id: UUID, activity_date: date
    ) -> list[PlannedWorkout]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT ws.id, ws.workout_type, ws.distance_km, ws.pace_zone,
                       ws.week_number, ws.phase,
                       tp.start_date + (
                           (ws.week_number - 1) * 7 +
                           CASE ws.day_of_week
                               WHEN 'Mon' THEN 0 WHEN 'Tue' THEN 1 WHEN 'Wed' THEN 2
                               WHEN 'Thu' THEN 3 WHEN 'Fri' THEN 4 WHEN 'Sat' THEN 5
                               WHEN 'Sun' THEN 6 ELSE 0 END
                       ) AS workout_date
                FROM workout_sessions ws
                JOIN training_plans tp ON ws.plan_id = tp.id
                WHERE tp.id = %s
                  AND tp.start_date + (
                      (ws.week_number - 1) * 7 +
                      CASE ws.day_of_week
                          WHEN 'Mon' THEN 0 WHEN 'Tue' THEN 1 WHEN 'Wed' THEN 2
                          WHEN 'Thu' THEN 3 WHEN 'Fri' THEN 4 WHEN 'Sat' THEN 5
                          WHEN 'Sun' THEN 6 ELSE 0 END
                  ) = %s
                """,
                (plan_id, activity_date),
            )
            rows = await cur.fetchall()
        return [
            PlannedWorkout(
                id=row["id"],
                date=row["workout_date"],
                workout_type=row["workout_type"],
                distance_km=float(row["distance_km"]) if row["distance_km"] else 0.0,
                pace_zone=row["pace_zone"] or "",
                week_number=row["week_number"],
                phase=row["phase"],
            )
            for row in rows
        ]


class StravaConnectionRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def upsert(
        self,
        athlete_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO strava_connections
                    (strava_athlete_id, access_token, refresh_token, expires_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (strava_athlete_id) DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at
                """,
                (athlete_id, access_token, refresh_token, expires_at),
            )

    async def get(self) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM strava_connections ORDER BY created_at DESC LIMIT 1"
            )
            return await cur.fetchone()

    async def update_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
    ) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE strava_connections
                SET access_token = %s, refresh_token = %s, expires_at = %s
                """,
                (access_token, refresh_token, expires_at),
            )

    async def delete(self) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute("DELETE FROM strava_connections")


class ActivityAnalysisRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def insert(
        self,
        strava_activity_id: int,
        matched_workout_id: UUID | None,
        activity_date: date,
        distance_km: float,
        avg_pace_per_km: timedelta | None,
        avg_hr_zone: str | None,
        pace_adherence: str | None,
        hr_adherence: str | None,
        load_adherence: str | None,
        mismatch: bool,
    ) -> UUID:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO activity_analyses
                    (strava_activity_id, matched_workout_id, activity_date,
                     distance_km, avg_pace_per_km, avg_hr_zone,
                     pace_adherence, hr_adherence, load_adherence, mismatch)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    strava_activity_id,
                    matched_workout_id,
                    activity_date,
                    distance_km,
                    avg_pace_per_km,
                    avg_hr_zone,
                    pace_adherence,
                    hr_adherence,
                    load_adherence,
                    mismatch,
                ),
            )
            row = await cur.fetchone()
            return row[0]

    async def get_by_strava_id(self, strava_activity_id: int) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM activity_analyses WHERE strava_activity_id = %s",
                (strava_activity_id,),
            )
            return await cur.fetchone()

    async def list_for_week(
        self, plan_id: UUID, week_number: int | None = None
    ) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            if week_number is not None:
                await cur.execute(
                    "SELECT start_date FROM training_plans WHERE id = %s",
                    (plan_id,),
                )
                plan_row = await cur.fetchone()
                if plan_row is None:
                    return []
                start_date = plan_row["start_date"]
                week_start = start_date + timedelta(days=(week_number - 1) * 7)
                week_end = week_start + timedelta(days=6)

                await cur.execute(
                    """
                    SELECT aa.id, aa.strava_activity_id, aa.matched_workout_id,
                           aa.activity_date, aa.distance_km, aa.avg_pace_per_km,
                           aa.avg_hr_zone, aa.pace_adherence, aa.hr_adherence,
                           aa.load_adherence, aa.mismatch, aa.created_at,
                           ws.day_of_week, ws.workout_type,
                           ws.distance_km AS planned_distance_km,
                           ws.pace_zone, ws.phase
                    FROM activity_analyses aa
                    LEFT JOIN workout_sessions ws ON aa.matched_workout_id = ws.id
                    WHERE aa.activity_date BETWEEN %s AND %s
                    ORDER BY aa.activity_date
                    """,
                    (week_start, week_end),
                )
            else:
                await cur.execute(
                    """
                    SELECT aa.id, aa.strava_activity_id, aa.matched_workout_id,
                           aa.activity_date, aa.distance_km, aa.avg_pace_per_km,
                           aa.avg_hr_zone, aa.pace_adherence, aa.hr_adherence,
                           aa.load_adherence, aa.mismatch, aa.created_at,
                           ws.day_of_week, ws.workout_type,
                           ws.distance_km AS planned_distance_km,
                           ws.pace_zone, ws.phase
                    FROM activity_analyses aa
                    LEFT JOIN workout_sessions ws ON aa.matched_workout_id = ws.id
                    ORDER BY aa.activity_date DESC
                    """
                )
            return await cur.fetchall()


class WeeklySummaryRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def upsert(self, plan_id: UUID, week_number: int, summary: str) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO weekly_summaries (plan_id, week_number, summary)
                VALUES (%s, %s, %s)
                ON CONFLICT (plan_id, week_number) DO UPDATE SET
                    summary = EXCLUDED.summary
                """,
                (plan_id, week_number, summary),
            )

    async def get_by_week(self, plan_id: UUID, week_number: int) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT * FROM weekly_summaries
                WHERE plan_id = %s AND week_number = %s
                """,
                (plan_id, week_number),
            )
            return await cur.fetchone()
