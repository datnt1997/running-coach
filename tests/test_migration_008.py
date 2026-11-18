import pytest


@pytest.mark.asyncio
async def test_migration_keeps_existing_goals_with_null_current_load():
    from psycopg import AsyncConnection

    from app.config import DATABASE_URL
    from tests import conftest as c

    if not DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")

    migration_008 = next(m for m in c.MIGRATIONS if m.name.startswith("008_"))
    before = [m for m in c.MIGRATIONS if m.name < migration_008.name]
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
        await conn.execute(
            "INSERT INTO user_goals (distance, target_time, race_date, weekly_availability, vdot)"
            f" VALUES ('half_marathon', '2:00:00', '2027-06-01', {week}, 42.0)"
        )

        await conn.execute(migration_008.read_text())

        cur = await conn.execute("SELECT vdot, weekly_km, longest_run_km FROM user_goals")
        rows = await cur.fetchall()

    assert rows == [(pytest.approx(42.0), None, None)]
