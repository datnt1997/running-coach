-- Rolling summary: older Plan chat messages compressed into one text per Runner.
-- Raw chat_messages are never deleted; covered_seq is the last message folded in.
CREATE TABLE chat_summaries (
    runner_id   UUID PRIMARY KEY REFERENCES runners(id),
    content     TEXT NOT NULL,
    covered_seq BIGINT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
