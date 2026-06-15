from datetime import timedelta
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.models.goal import GoalRequest


def _parse_target_time(target_time: str) -> timedelta:
    """Parse an HH:MM:SS string into a timedelta for the INTERVAL column."""
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


class PlanRepository:
    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def insert_plan(
        self, goal_id: UUID, total_weeks: int, summary: str
    ) -> UUID:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO training_plans (goal_id, total_weeks, summary)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (goal_id, total_weeks, summary),
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
        """Return the full plan with its goal id and all workout sessions.

        Returns None if the plan does not exist. Workouts are grouped into
        weeks, ordered by week number and the canonical day-of-week order.
        """
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, goal_id, total_weeks, summary
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
