CREATE TABLE user_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distance TEXT NOT NULL,
    target_time INTERVAL NOT NULL,
    race_date DATE NOT NULL,
    fitness_level TEXT NOT NULL,
    days_per_week INT NOT NULL,
    injury_history TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE training_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID REFERENCES user_goals(id),
    total_weeks INT NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE workout_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID REFERENCES training_plans(id),
    week_number INT NOT NULL,
    phase TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    workout_type TEXT NOT NULL,
    distance_km NUMERIC(5,2),
    pace_zone TEXT,
    notes TEXT
);
