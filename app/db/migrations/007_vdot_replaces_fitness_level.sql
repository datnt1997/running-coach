-- VDOT is the only fitness input; the beginner/intermediate/advanced label is gone (issue #17).
-- Goals saved without a VDOT have no fitness signal left, so they are deleted
-- together with their plans (approved: the only data was the owner's own).
UPDATE activity_analyses SET matched_workout_id = NULL
WHERE matched_workout_id IN (
    SELECT ws.id FROM workout_sessions ws
    JOIN training_plans tp ON ws.plan_id = tp.id
    JOIN user_goals g ON tp.goal_id = g.id
    WHERE g.vdot IS NULL
);
DELETE FROM weekly_summaries WHERE plan_id IN (
    SELECT tp.id FROM training_plans tp JOIN user_goals g ON tp.goal_id = g.id WHERE g.vdot IS NULL
);
DELETE FROM workout_sessions WHERE plan_id IN (
    SELECT tp.id FROM training_plans tp JOIN user_goals g ON tp.goal_id = g.id WHERE g.vdot IS NULL
);
DELETE FROM training_plans WHERE goal_id IN (SELECT id FROM user_goals WHERE vdot IS NULL);
DELETE FROM user_goals WHERE vdot IS NULL;

ALTER TABLE user_goals ALTER COLUMN vdot SET NOT NULL;
ALTER TABLE user_goals DROP COLUMN fitness_level;
