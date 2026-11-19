-- Runner ownership: every Goal, Plan, Strava connection, Activity analysis and
-- Weekly summary belongs to exactly one Runner.
--
-- Expand (runners table, nullable runner_id), backfill (the first Runner owns
-- every existing row), contract (runner_id NOT NULL).
--
-- The first Runner is the allowlisted owner. Pass their email when applying:
--   PGOPTIONS="-c app.owner_email=you@example.com" psql "$DATABASE_URL" -f 009_runner_ownership.sql
-- On a database that already holds rows the email is required; on an empty one
-- it may be omitted (Runners are created at sign-in).

CREATE TABLE runners (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email      TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT runners_email_lowercase CHECK (email = lower(email))
);

-- expand
ALTER TABLE user_goals         ADD COLUMN runner_id UUID REFERENCES runners(id);
ALTER TABLE training_plans     ADD COLUMN runner_id UUID REFERENCES runners(id);
ALTER TABLE strava_connections ADD COLUMN runner_id UUID REFERENCES runners(id);
ALTER TABLE activity_analyses  ADD COLUMN runner_id UUID REFERENCES runners(id);
ALTER TABLE weekly_summaries   ADD COLUMN runner_id UUID REFERENCES runners(id);

-- backfill
DO $$
DECLARE
    owner_email TEXT := nullif(trim(coalesce(current_setting('app.owner_email', true), '')), '');
    has_rows BOOLEAN;
    first_runner UUID;
BEGIN
    SELECT EXISTS (SELECT 1 FROM user_goals)
        OR EXISTS (SELECT 1 FROM training_plans)
        OR EXISTS (SELECT 1 FROM strava_connections)
        OR EXISTS (SELECT 1 FROM activity_analyses)
        OR EXISTS (SELECT 1 FROM weekly_summaries)
    INTO has_rows;

    IF owner_email IS NULL THEN
        IF has_rows THEN
            RAISE EXCEPTION 'Existing data needs an owner: set app.owner_email to the allowlisted owner email (PGOPTIONS="-c app.owner_email=...")';
        END IF;
        RETURN;
    END IF;

    INSERT INTO runners (email) VALUES (lower(owner_email))
    ON CONFLICT (email) DO NOTHING;
    SELECT id INTO first_runner FROM runners WHERE email = lower(owner_email);

    UPDATE user_goals         SET runner_id = first_runner;
    UPDATE training_plans     SET runner_id = first_runner;
    UPDATE strava_connections SET runner_id = first_runner;
    UPDATE activity_analyses  SET runner_id = first_runner;
    UPDATE weekly_summaries   SET runner_id = first_runner;
END $$;

-- contract
ALTER TABLE user_goals         ALTER COLUMN runner_id SET NOT NULL;
ALTER TABLE training_plans     ALTER COLUMN runner_id SET NOT NULL;
ALTER TABLE strava_connections ALTER COLUMN runner_id SET NOT NULL;
ALTER TABLE activity_analyses  ALTER COLUMN runner_id SET NOT NULL;
ALTER TABLE weekly_summaries   ALTER COLUMN runner_id SET NOT NULL;

-- one Strava connection per Runner (an athlete is already unique)
ALTER TABLE strava_connections ADD CONSTRAINT strava_connections_runner_key UNIQUE (runner_id);

CREATE INDEX user_goals_runner_idx        ON user_goals (runner_id);
CREATE INDEX training_plans_runner_idx    ON training_plans (runner_id);
CREATE INDEX activity_analyses_runner_idx ON activity_analyses (runner_id);
CREATE INDEX weekly_summaries_runner_idx  ON weekly_summaries (runner_id);
