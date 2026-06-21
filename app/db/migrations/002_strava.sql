ALTER TABLE training_plans ADD COLUMN start_date DATE NOT NULL DEFAULT CURRENT_DATE;

CREATE TABLE strava_connections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strava_athlete_id BIGINT NOT NULL UNIQUE,
    access_token      TEXT NOT NULL,
    refresh_token     TEXT NOT NULL,
    expires_at        TIMESTAMPTZ NOT NULL,
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE activity_analyses (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strava_activity_id BIGINT NOT NULL UNIQUE,
    matched_workout_id UUID REFERENCES workout_sessions(id),
    activity_date      DATE NOT NULL,
    distance_km        NUMERIC(5,2) NOT NULL,
    avg_pace_per_km    INTERVAL,
    avg_hr_zone        TEXT,
    pace_adherence     TEXT,
    hr_adherence       TEXT,
    load_adherence     TEXT,
    mismatch           BOOLEAN NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE weekly_summaries (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id     UUID REFERENCES training_plans(id),
    week_number INT NOT NULL,
    summary     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (plan_id, week_number)
);
