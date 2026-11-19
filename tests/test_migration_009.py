import pytest

_WEEK = (
    "'[" + ",".join(
        f'{{"day": "{d}", "slots": 1, "maxKm": null, "qualityAllowed": true}}'
        for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    ) + "]'"
)
_OWNER = "Runner@Example.com"


async def _apply_before_009():
    from psycopg import AsyncConnection

    from app.config import DATABASE_URL
    from tests import conftest as c

    if not DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")
    migration_009 = next(m for m in c.MIGRATIONS if m.name.startswith("009_"))
    conn = await AsyncConnection.connect(DATABASE_URL, autocommit=True)
    await conn.execute(f"DROP TABLE IF EXISTS {c._ALL_TABLES} CASCADE")
    for migration in (m for m in c.MIGRATIONS if m.name < migration_009.name):
        await conn.execute(migration.read_text())
    return conn, migration_009


async def _seed_one_of_each(conn):
    await conn.execute(
        "INSERT INTO user_goals (id, distance, target_time, race_date, weekly_availability, vdot)"
        f" VALUES ('00000000-0000-0000-0000-000000000001', 'half_marathon', '2:00:00', '2027-06-01', {_WEEK}, 42.0)"
    )
    await conn.execute(
        "INSERT INTO training_plans (id, goal_id, total_weeks, summary)"
        " VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 4, 'Plan')"
    )
    await conn.execute(
        "INSERT INTO workout_sessions (plan_id, week_number, phase, day_of_week, workout_type, distance_km)"
        " VALUES ('00000000-0000-0000-0000-000000000002', 1, 'base', 'Mon', 'easy', 8)"
    )
    await conn.execute(
        "INSERT INTO strava_connections (strava_athlete_id, access_token, refresh_token, expires_at)"
        " VALUES (12345, 'a', 'r', '2099-01-01')"
    )
    await conn.execute(
        "INSERT INTO activity_analyses (strava_activity_id, activity_date, distance_km)"
        " VALUES (777, '2027-01-01', 8)"
    )
    await conn.execute(
        "INSERT INTO weekly_summaries (plan_id, week_number, summary)"
        " VALUES ('00000000-0000-0000-0000-000000000002', 1, 'Good week')"
    )


_OWNED = ("user_goals", "training_plans", "strava_connections", "activity_analyses", "weekly_summaries")


@pytest.mark.asyncio
async def test_existing_rows_land_on_the_first_runner_unchanged():
    conn, migration = await _apply_before_009()
    async with conn:
        await _seed_one_of_each(conn)
        await conn.execute(f"SET app.owner_email = '{_OWNER}'")
        await conn.execute(migration.read_text())

        cur = await conn.execute("SELECT id, email FROM runners")
        runners = await cur.fetchall()
        assert [r[1] for r in runners] == ["runner@example.com"]
        first = runners[0][0]

        for table in _OWNED:
            cur = await conn.execute(f"SELECT runner_id FROM {table}")
            assert [r[0] for r in await cur.fetchall()] == [first], table

        # Contents unchanged
        cur = await conn.execute("SELECT distance, vdot FROM user_goals")
        assert await cur.fetchall() == [("half_marathon", pytest.approx(42.0))]
        cur = await conn.execute("SELECT summary FROM training_plans")
        assert await cur.fetchall() == [("Plan",)]
        cur = await conn.execute("SELECT strava_athlete_id FROM strava_connections")
        assert await cur.fetchall() == [(12345,)]
        cur = await conn.execute("SELECT strava_activity_id FROM activity_analyses")
        assert await cur.fetchall() == [(777,)]
        cur = await conn.execute("SELECT summary FROM weekly_summaries")
        assert await cur.fetchall() == [("Good week",)]


@pytest.mark.asyncio
async def test_ownership_is_mandatory_after_the_migration():
    from psycopg import errors

    conn, migration = await _apply_before_009()
    async with conn:
        await conn.execute(f"SET app.owner_email = '{_OWNER}'")
        await conn.execute(migration.read_text())
        with pytest.raises(errors.NotNullViolation):
            await conn.execute(
                "INSERT INTO user_goals (distance, target_time, race_date, weekly_availability, vdot)"
                f" VALUES ('half_marathon', '2:00:00', '2027-06-01', {_WEEK}, 42.0)"
            )
        with pytest.raises(errors.NotNullViolation):
            await conn.execute(
                "INSERT INTO activity_analyses (strava_activity_id, activity_date, distance_km)"
                " VALUES (1, '2027-01-01', 8)"
            )


@pytest.mark.asyncio
async def test_existing_data_without_an_owner_email_is_refused():
    from psycopg import errors

    conn, migration = await _apply_before_009()
    async with conn:
        await _seed_one_of_each(conn)
        with pytest.raises(errors.RaiseException):
            await conn.execute(migration.read_text())


@pytest.mark.asyncio
async def test_empty_database_migrates_without_an_owner_email():
    conn, migration = await _apply_before_009()
    async with conn:
        await conn.execute(migration.read_text())
        cur = await conn.execute("SELECT count(*) FROM runners")
        assert (await cur.fetchone())[0] == 0
