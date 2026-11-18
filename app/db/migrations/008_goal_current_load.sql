-- The runner's current weekly distance and longest recent run now reach the plan
-- prompt. Existing Goals never recorded them, so the columns stay nullable; the
-- API requires both for every new Goal.
ALTER TABLE user_goals ADD COLUMN weekly_km REAL;
ALTER TABLE user_goals ADD COLUMN longest_run_km REAL;
