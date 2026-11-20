-- Runner profile: the personal numbers the coach uses (heart rates, cadence).
-- One row per Runner; every value is optional until the runner enters it.
CREATE TABLE runner_profiles (
    runner_id            UUID PRIMARY KEY REFERENCES runners(id),
    max_hr               INTEGER CHECK (max_hr BETWEEN 100 AND 230),
    lactate_threshold_hr INTEGER CHECK (lactate_threshold_hr BETWEEN 80 AND 220),
    resting_hr           INTEGER CHECK (resting_hr BETWEEN 25 AND 120),
    cadence              INTEGER CHECK (cadence BETWEEN 120 AND 230),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
