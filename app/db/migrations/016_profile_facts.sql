-- Profile facts: durable things the coach knows about the Runner, saved only after
-- the Runner confirms a proposal made in the Plan chat.
CREATE TABLE profile_facts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seq        BIGINT GENERATED ALWAYS AS IDENTITY,
    runner_id  UUID NOT NULL REFERENCES runners(id),
    text       TEXT NOT NULL CHECK (length(text) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX profile_facts_runner_seq_idx ON profile_facts (runner_id, seq);

-- A coach reply may carry one proposed fact; it stays pending until the Runner decides.
ALTER TABLE chat_messages
    ADD COLUMN proposed_fact TEXT CHECK (proposed_fact IS NULL OR length(proposed_fact) > 0),
    ADD COLUMN proposal_status TEXT CHECK (proposal_status IN ('pending', 'saved', 'declined')),
    ADD CONSTRAINT chat_messages_proposal_check
        CHECK ((proposed_fact IS NULL) = (proposal_status IS NULL));
