import pytest


@pytest.mark.asyncio
async def test_migration_drops_fitness_level_and_deletes_goals_without_vdot():
    from psycopg import AsyncConnection

    from app.config import DATABASE_URL
    from tests import conftest as c

    if not DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")

    migration_007 = next(m for m in c.MIGRATIONS if m.name.startswith("007_"))
    before = [m for m in c.MIGRATIONS if m.name < migration_007.name]
    week = (
        "'[" + ",".join(
            f'{{"day": "{d}", "slots": 1, "maxKm": null, "qualityAllowed": true}}'
            for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        ) + "]'"
    )
    async with await AsyncConnection.connect(DATABASE_URL, autocommit=True) as conn:
        await conn.execute(f"DROP TABLE IF EXISTS {c._ALL_TABLES} CASCADE")
        for migration in before:
            await conn.execute(migration.read_text())
        for vdot in ("NULL", "42.0"):
            await conn.execute(
                "INSERT INTO user_goals (distance, target_time, race_date, fitness_level,"
                f" weekly_availability, vdot) VALUES ('half_marathon', '2:00:00', '2027-06-01',"
                f" 'intermediate', {week}, {vdot})"
            )
        await conn.execute(
            "INSERT INTO training_plans (goal_id, total_weeks, summary, start_date)"
            " SELECT id, 12, 'old', '2026-11-01' FROM user_goals WHERE vdot IS NULL"
        )
        await conn.execute(
            "INSERT INTO workout_sessions (plan_id, week_number, phase, day_of_week, workout_type)"
            " SELECT id, 1, 'base', 'Mon', 'easy' FROM training_plans"
        )

        await conn.execute(migration_007.read_text())

        cur = await conn.execute("SELECT vdot FROM user_goals")
        vdots = [row[0] for row in await cur.fetchall()]
        plans = (await (await conn.execute("SELECT count(*) FROM training_plans")).fetchone())[0]
        cur = await conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'user_goals'"
        )
        columns = {row[0] for row in await cur.fetchall()}

    assert vdots == [pytest.approx(42.0)]
    assert plans == 0
    assert "fitness_level" not in columns
