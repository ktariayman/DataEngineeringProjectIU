-- =============================================================================
-- Migration 01 — Recommendations Table (Serving Store)
-- =============================================================================
-- Stores precomputed collaborative-filtering recommendations.
-- Written by: Recommendation Loader (batch job)
-- Read by:    Recommendation API (GET /v1/recommendations/me)
--
-- Privacy NFR  : stores anonymized IDs + score only — no names, no emails
-- Security NFR : read-only from API perspective; only loader has INSERT rights
-- Governance   : generation_date stored so consumers know data freshness
-- Scalability  : two indexes for fast per-user and per-date lookups

CREATE TABLE IF NOT EXISTS recommendations (
    id                  BIGSERIAL       PRIMARY KEY,
    user_id             VARCHAR(64)     NOT NULL,
    recommended_user_id VARCHAR(64)     NOT NULL,
    similarity_score    DOUBLE PRECISION NOT NULL,
    generation_date     DATE            NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Idempotency: one recommendation per user pair per day
    CONSTRAINT uq_rec_user_pair_date UNIQUE (user_id, recommended_user_id, generation_date)
);

-- Index 1: primary access pattern — "give me recommendations for user X on the latest date"
CREATE INDEX IF NOT EXISTS ix_rec_user_date
    ON recommendations (user_id, generation_date DESC);

-- Index 2: used by the loader to delete/replace old windows (retention cleanup)
CREATE INDEX IF NOT EXISTS ix_rec_gen_date
    ON recommendations (generation_date);

COMMENT ON TABLE recommendations IS
    'Precomputed collaborative-filtering recommendations. Populated by recommendation_loader batch job.';
COMMENT ON COLUMN recommendations.user_id IS
    'Anonymized learner ID — maps to EdNet KT4 user identifier.';
COMMENT ON COLUMN recommendations.recommended_user_id IS
    'Anonymized ID of the similar learner being recommended.';
COMMENT ON COLUMN recommendations.similarity_score IS
    'Cosine similarity in [0,1]. Higher = more similar learning path.';
COMMENT ON COLUMN recommendations.generation_date IS
    'UTC date when this recommendation batch was generated. Used for freshness checks.';
