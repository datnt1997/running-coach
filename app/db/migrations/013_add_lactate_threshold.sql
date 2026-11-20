-- Optional lactate-threshold HR, used only when analysing activities; zones ignore it.
ALTER TABLE runner_profiles ADD COLUMN IF NOT EXISTS lactate_threshold_hr INTEGER
    CHECK (lactate_threshold_hr BETWEEN 80 AND 220);
