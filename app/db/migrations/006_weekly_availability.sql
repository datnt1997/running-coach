-- Weekly availability replaces days_per_week (docs/adr/0001).
-- Existing goals: N days become N one-slot days, no cap, Quality workouts allowed.
-- The days are taken in the order Mon, Wed, Fri, Sat, Tue, Thu, Sun, because the
-- old data recorded only how many days, not which.
ALTER TABLE user_goals ADD COLUMN weekly_availability JSONB;

UPDATE user_goals
SET weekly_availability = (
    SELECT jsonb_agg(
        jsonb_build_object(
            'day', d.day,
            'slots', CASE WHEN d.pick_order <= user_goals.days_per_week THEN 1 ELSE 0 END,
            'maxKm', NULL,
            'qualityAllowed', true
        )
        ORDER BY d.week_order
    )
    FROM (VALUES
        ('Mon', 1, 1), ('Tue', 2, 5), ('Wed', 3, 2), ('Thu', 4, 6),
        ('Fri', 5, 3), ('Sat', 6, 4), ('Sun', 7, 7)
    ) AS d(day, week_order, pick_order)
);

ALTER TABLE user_goals ALTER COLUMN weekly_availability SET NOT NULL;
ALTER TABLE user_goals DROP COLUMN days_per_week;
