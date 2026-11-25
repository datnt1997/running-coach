-- Plan edits proposed in the Plan chat. A proposal that passes the Python checks is
-- pending until the Runner confirms (applied) or declines it; one that fails is kept
-- as rejected with its reasons. The applied rows are the edit log.
CREATE TABLE plan_edits (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq         BIGINT GENERATED ALWAYS AS IDENTITY,
    runner_id   UUID NOT NULL REFERENCES runners(id),
    plan_id     UUID NOT NULL REFERENCES training_plans(id) ON DELETE CASCADE,
    request     TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL CHECK (status IN ('pending', 'applied', 'declined', 'rejected')),
    -- [{week, day, before: [workout], after: [workout]}] for each changed day
    changes     JSONB NOT NULL DEFAULT '[]',
    -- {week, day, limits: [reason]}: the one day on which Weekly availability is broken on purpose
    override    JSONB,
    -- [{code, params}] why the edit was rejected
    reasons     JSONB,
    -- {week: km}: each changed week's total before this edit, so the first one is the Weekly volume
    week_totals JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at  TIMESTAMPTZ
);

CREATE INDEX plan_edits_runner_seq_idx ON plan_edits (runner_id, seq);

-- The coach reply that carries the proposal (or the rejection).
ALTER TABLE chat_messages
    ADD COLUMN plan_edit_id UUID REFERENCES plan_edits(id) ON DELETE SET NULL;
