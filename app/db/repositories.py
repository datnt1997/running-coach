from datetime import date, datetime, timedelta
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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
    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def insert(self, goal: GoalRequest) -> UUID:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO user_goals
                    (distance, target_time, race_date,
                     weekly_availability, injury_history, vdot,
                     weekly_km, longest_run_km, runner_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    goal.distance,
                    _parse_target_time(goal.target_time),
                    goal.race_date,
                    Jsonb([d.model_dump(by_alias=True) for d in goal.weekly_availability]),
                    goal.injury_history,
                    goal.vdot,
                    goal.weekly_km,
                    goal.longest_run_km,
                    self.runner_id,
                ),
            )
            row = await cur.fetchone()
            return row[0]

    async def get(self, goal_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM user_goals WHERE id = %s AND runner_id = %s",
                (goal_id, self.runner_id),
            )
            return await cur.fetchone()

    async def update_status(self, goal_id: UUID, status: str) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE user_goals SET plan_status = %s WHERE id = %s AND runner_id = %s",
                (status, goal_id, self.runner_id),
            )

    async def list_all(self) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, distance, target_time, race_date, vdot,
                       weekly_availability, plan_status, created_at
                FROM user_goals
                WHERE runner_id = %s
                ORDER BY created_at DESC
                """,
                (self.runner_id,),
            )
            return await cur.fetchall()

    async def delete(self, goal_id: UUID) -> bool:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM user_goals WHERE id = %s AND runner_id = %s",
                (goal_id, self.runner_id),
            )
            if await cur.fetchone() is None:
                return False
            # Null out FK references from activity_analyses to workouts being deleted
            await cur.execute(
                """
                UPDATE activity_analyses SET matched_workout_id = NULL
                WHERE runner_id = %s AND matched_workout_id IN (
                    SELECT ws.id FROM workout_sessions ws
                    JOIN training_plans tp ON ws.plan_id = tp.id
                    WHERE tp.goal_id = %s AND tp.runner_id = %s
                )
                """,
                (self.runner_id, goal_id, self.runner_id),
            )
            await cur.execute(
                "DELETE FROM weekly_summaries WHERE runner_id = %s"
                " AND plan_id IN (SELECT id FROM training_plans WHERE goal_id = %s AND runner_id = %s)",
                (self.runner_id, goal_id, self.runner_id),
            )
            await cur.execute(
                "DELETE FROM workout_sessions"
                " WHERE plan_id IN (SELECT id FROM training_plans WHERE goal_id = %s AND runner_id = %s)",
                (goal_id, self.runner_id),
            )
            await cur.execute(
                "DELETE FROM training_plans WHERE goal_id = %s AND runner_id = %s",
                (goal_id, self.runner_id),
            )
            await cur.execute(
                "DELETE FROM user_goals WHERE id = %s AND runner_id = %s RETURNING id",
                (goal_id, self.runner_id),
            )
            row = await cur.fetchone()
            return row is not None


class PlanRepository:
    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def insert_plan(
        self,
        goal_id: UUID,
        total_weeks: int,
        summary: str,
        start_date: date | None = None,
        language: str = "vi",
    ) -> UUID:
        if start_date is None:
            start_date = date.today()
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO training_plans (goal_id, total_weeks, summary, start_date, language, runner_id)
                SELECT g.id, %s, %s, %s, %s, g.runner_id FROM user_goals g
                WHERE g.id = %s AND g.runner_id = %s
                RETURNING id
                """,
                (total_weeks, summary, start_date, language, goal_id, self.runner_id),
            )
            row = await cur.fetchone()
            if row is None:
                raise LookupError("Goal not found for this runner")
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
                SELECT tp.id, %s, %s, %s, %s, %s, %s, %s FROM training_plans tp
                WHERE tp.id = %s AND tp.runner_id = %s
                """,
                (
                    week_number,
                    phase,
                    day,
                    workout_type,
                    distance_km,
                    pace_zone,
                    notes,
                    plan_id,
                    self.runner_id,
                ),
            )
            if cur.rowcount != 1:
                raise LookupError("Plan not found for this runner")

    async def get_plan(self, plan_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, goal_id, total_weeks, summary, start_date, language
                FROM training_plans
                WHERE id = %s AND runner_id = %s
                """,
                (plan_id, self.runner_id),
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
                "SELECT id, goal_id, total_weeks, summary, start_date, language FROM training_plans"
                " WHERE goal_id = %s AND runner_id = %s",
                (goal_id, self.runner_id),
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
                "SELECT id FROM training_plans WHERE runner_id = %s ORDER BY created_at DESC LIMIT 1",
                (self.runner_id,),
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
                WHERE tp.id = %s AND tp.runner_id = %s
                  AND tp.start_date + (
                      (ws.week_number - 1) * 7 +
                      CASE ws.day_of_week
                          WHEN 'Mon' THEN 0 WHEN 'Tue' THEN 1 WHEN 'Wed' THEN 2
                          WHEN 'Thu' THEN 3 WHEN 'Fri' THEN 4 WHEN 'Sat' THEN 5
                          WHEN 'Sun' THEN 6 ELSE 0 END
                  ) = %s
                """,
                (plan_id, self.runner_id, activity_date),
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
    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

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
                    (strava_athlete_id, access_token, refresh_token, expires_at, runner_id)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (runner_id) DO UPDATE SET
                    strava_athlete_id = EXCLUDED.strava_athlete_id,
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    expires_at = EXCLUDED.expires_at
                """,
                (athlete_id, access_token, refresh_token, expires_at, self.runner_id),
            )

    async def get(self) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM strava_connections WHERE runner_id = %s", (self.runner_id,)
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
                WHERE runner_id = %s
                """,
                (access_token, refresh_token, expires_at, self.runner_id),
            )

    async def delete(self) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute("DELETE FROM strava_connections WHERE runner_id = %s", (self.runner_id,))


class ActivityAnalysisRepository:
    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

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
        avg_hr_bpm: float | None = None,
    ) -> UUID:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO activity_analyses
                    (strava_activity_id, matched_workout_id, activity_date,
                     distance_km, avg_pace_per_km, avg_hr_zone,
                     pace_adherence, hr_adherence, load_adherence, mismatch, runner_id,
                     avg_hr_bpm)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    self.runner_id,
                    avg_hr_bpm,
                ),
            )
            row = await cur.fetchone()
            return row[0]

    async def get_by_strava_id(self, strava_activity_id: int) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM activity_analyses WHERE strava_activity_id = %s AND runner_id = %s",
                (strava_activity_id, self.runner_id),
            )
            return await cur.fetchone()

    async def by_strava_ids(self, strava_activity_ids: list[int]) -> dict[int, dict]:
        """Analyses for these Strava activities, keyed by Strava id, with the matched workout's type."""
        if not strava_activity_ids:
            return {}
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT aa.strava_activity_id, aa.pace_adherence, aa.hr_adherence, aa.load_adherence,
                       aa.mismatch, aa.matched_workout_id, ws.workout_type,
                       ws.distance_km AS planned_distance_km
                FROM activity_analyses aa
                LEFT JOIN workout_sessions ws ON aa.matched_workout_id = ws.id
                WHERE aa.runner_id = %s AND aa.strava_activity_id = ANY(%s)
                """,
                (self.runner_id, strava_activity_ids),
            )
            return {r["strava_activity_id"]: r for r in await cur.fetchall()}

    async def list_recent(self, limit: int) -> list[dict]:
        """The Runner's latest Activities, newest first, with their Match (if any)."""
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT aa.activity_date, aa.distance_km, aa.avg_hr_bpm, aa.pace_adherence,
                       aa.hr_adherence, aa.load_adherence, aa.mismatch,
                       aa.matched_workout_id, ws.workout_type,
                       ws.distance_km AS planned_distance_km
                FROM activity_analyses aa
                LEFT JOIN workout_sessions ws ON aa.matched_workout_id = ws.id
                WHERE aa.runner_id = %s
                ORDER BY aa.activity_date DESC, aa.created_at DESC
                LIMIT %s
                """,
                (self.runner_id, limit),
            )
            return await cur.fetchall()

    async def list_for_week(
        self, plan_id: UUID, week_number: int | None = None
    ) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            if week_number is not None:
                await cur.execute(
                    "SELECT start_date FROM training_plans WHERE id = %s AND runner_id = %s",
                    (plan_id, self.runner_id),
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
                           aa.avg_hr_zone, aa.avg_hr_bpm, aa.pace_adherence, aa.hr_adherence,
                           aa.load_adherence, aa.mismatch, aa.created_at,
                           ws.day_of_week, ws.workout_type,
                           ws.distance_km AS planned_distance_km,
                           ws.pace_zone, ws.phase
                    FROM activity_analyses aa
                    LEFT JOIN workout_sessions ws ON aa.matched_workout_id = ws.id
                    WHERE aa.runner_id = %s AND aa.activity_date BETWEEN %s AND %s
                    ORDER BY aa.activity_date
                    """,
                    (self.runner_id, week_start, week_end),
                )
            else:
                await cur.execute(
                    """
                    SELECT aa.id, aa.strava_activity_id, aa.matched_workout_id,
                           aa.activity_date, aa.distance_km, aa.avg_pace_per_km,
                           aa.avg_hr_zone, aa.avg_hr_bpm, aa.pace_adherence, aa.hr_adherence,
                           aa.load_adherence, aa.mismatch, aa.created_at,
                           ws.day_of_week, ws.workout_type,
                           ws.distance_km AS planned_distance_km,
                           ws.pace_zone, ws.phase
                    FROM activity_analyses aa
                    LEFT JOIN workout_sessions ws ON aa.matched_workout_id = ws.id
                    WHERE aa.runner_id = %s
                    ORDER BY aa.activity_date DESC
                    """,
                    (self.runner_id,),
                )
            return await cur.fetchall()


class WeeklySummaryRepository:
    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def upsert(self, plan_id: UUID, week_number: int, summary: str) -> None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO weekly_summaries (plan_id, week_number, summary, runner_id)
                SELECT tp.id, %s, %s, tp.runner_id FROM training_plans tp
                WHERE tp.id = %s AND tp.runner_id = %s
                ON CONFLICT (plan_id, week_number) DO UPDATE SET
                    summary = EXCLUDED.summary
                """,
                (week_number, summary, plan_id, self.runner_id),
            )
            if cur.rowcount != 1:
                raise LookupError("Plan not found for this runner")

    async def get_by_week(self, plan_id: UUID, week_number: int) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT * FROM weekly_summaries
                WHERE plan_id = %s AND week_number = %s AND runner_id = %s
                """,
                (plan_id, week_number, self.runner_id),
            )
            return await cur.fetchone()


class ProfileRepository:
    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def get(self) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT max_hr, lactate_threshold_hr, resting_hr"
                " FROM runner_profiles WHERE runner_id = %s",
                (self.runner_id,),
            )
            return await cur.fetchone()

    async def save(self, profile) -> None:
        """Replace this runner's profile with the values in a ProfileRequest."""
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO runner_profiles
                    (runner_id, max_hr, lactate_threshold_hr, resting_hr)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (runner_id) DO UPDATE SET
                    max_hr = EXCLUDED.max_hr,
                    lactate_threshold_hr = EXCLUDED.lactate_threshold_hr,
                    resting_hr = EXCLUDED.resting_hr,
                    updated_at = now()
                """,
                (self.runner_id, profile.max_hr, profile.lactate_threshold_hr,
                 profile.resting_hr),
            )


_CHAT_COLUMNS = "id, role, content, created_at, proposed_fact, proposal_status"


class ChatMessageRepository:
    """The Runner's one Plan chat conversation, oldest first."""

    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def add(self, role: str, content: str, proposed_fact: str | None = None) -> dict:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "INSERT INTO chat_messages (runner_id, role, content, proposed_fact, proposal_status)"
                " VALUES (%s, %s, %s, %s, %s)"
                f" RETURNING {_CHAT_COLUMNS}",
                (self.runner_id, role, content, proposed_fact, "pending" if proposed_fact else None),
            )
            return await cur.fetchone()

    async def decide_proposal(self, message_id: UUID, status: str) -> dict | None:
        """Move a pending proposal to `status`; None when there is no such pending proposal."""
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "UPDATE chat_messages SET proposal_status = %s"
                " WHERE id = %s AND runner_id = %s AND proposal_status = 'pending'"
                f" RETURNING {_CHAT_COLUMNS}",
                (status, message_id, self.runner_id),
            )
            return await cur.fetchone()

    async def get(self, message_id: UUID) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT {_CHAT_COLUMNS} FROM chat_messages WHERE id = %s AND runner_id = %s",
                (message_id, self.runner_id),
            )
            return await cur.fetchone()

    async def list_all(self) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT {_CHAT_COLUMNS} FROM chat_messages"
                " WHERE runner_id = %s ORDER BY seq",
                (self.runner_id,),
            )
            return await cur.fetchall()

    async def list_recent(self, limit: int) -> list[dict]:
        """The last `limit` messages, oldest first."""
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT {_CHAT_COLUMNS} FROM ("
                "  SELECT * FROM chat_messages WHERE runner_id = %s ORDER BY seq DESC LIMIT %s"
                ") recent ORDER BY seq",
                (self.runner_id, limit),
            )
            return await cur.fetchall()

    async def list_after(self, seq: int) -> list[dict]:
        """Messages with a sequence number above `seq`, oldest first (each carries its `seq`)."""
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT {_CHAT_COLUMNS}, seq FROM chat_messages"
                " WHERE runner_id = %s AND seq > %s ORDER BY seq",
                (self.runner_id, seq),
            )
            return await cur.fetchall()

    async def recent_declined_facts(self, limit: int) -> list[str]:
        """Texts of the last `limit` declined proposals, newest first."""
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT proposed_fact FROM chat_messages"
                " WHERE runner_id = %s AND proposal_status = 'declined'"
                " ORDER BY seq DESC LIMIT %s",
                (self.runner_id, limit),
            )
            return [row[0] for row in await cur.fetchall()]

    async def last(self) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT {_CHAT_COLUMNS} FROM chat_messages"
                " WHERE runner_id = %s ORDER BY seq DESC LIMIT 1",
                (self.runner_id,),
            )
            return await cur.fetchone()


class RollingSummaryRepository:
    """The Runner's Rolling summary of Plan chat messages older than the verbatim window."""

    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def get(self) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT content, covered_seq FROM chat_summaries WHERE runner_id = %s",
                (self.runner_id,),
            )
            return await cur.fetchone()

    async def save(self, content: str, covered_seq: int) -> None:
        await self.conn.execute(
            "INSERT INTO chat_summaries (runner_id, content, covered_seq) VALUES (%s, %s, %s)"
            " ON CONFLICT (runner_id) DO UPDATE"
            " SET content = EXCLUDED.content, covered_seq = EXCLUDED.covered_seq, updated_at = now()",
            (self.runner_id, content, covered_seq),
        )


_FACT_COLUMNS = "id, text, created_at, updated_at"


class ProfileFactRepository:
    """What the coach remembers about the Runner, oldest first."""

    def __init__(self, conn: AsyncConnection, runner_id: UUID):
        self.conn = conn
        self.runner_id = runner_id

    async def add(self, text: str) -> dict:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "INSERT INTO profile_facts (runner_id, text) VALUES (%s, %s)"
                f" RETURNING {_FACT_COLUMNS}",
                (self.runner_id, text),
            )
            return await cur.fetchone()

    async def list_all(self) -> list[dict]:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT {_FACT_COLUMNS} FROM profile_facts"
                " WHERE runner_id = %s ORDER BY seq",
                (self.runner_id,),
            )
            return await cur.fetchall()

    async def update(self, fact_id: UUID, text: str) -> dict | None:
        async with self.conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "UPDATE profile_facts SET text = %s, updated_at = now()"
                f" WHERE id = %s AND runner_id = %s RETURNING {_FACT_COLUMNS}",
                (text, fact_id, self.runner_id),
            )
            return await cur.fetchone()

    async def delete(self, fact_id: UUID) -> bool:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM profile_facts WHERE id = %s AND runner_id = %s",
                (fact_id, self.runner_id),
            )
            return cur.rowcount > 0


class RunnerRepository:
    """Runners themselves are not owned, so this one is not scoped."""

    def __init__(self, conn: AsyncConnection):
        self.conn = conn

    async def get_or_create(self, email: str) -> UUID:
        """The Runner with this (already normalized) email, created on first sign-in."""
        async with self.conn.cursor() as cur:
            await cur.execute("SELECT id FROM runners WHERE email = %s", (email,))
            row = await cur.fetchone()
            if row is None:
                await cur.execute(
                    "INSERT INTO runners (email) VALUES (%s)"
                    " ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email RETURNING id",
                    (email,),
                )
                row = await cur.fetchone()
            return row[0]

    async def find_runner_id_by_strava_athlete(self, athlete_id: int) -> UUID | None:
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT runner_id FROM strava_connections WHERE strava_athlete_id = %s",
                (athlete_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else None
