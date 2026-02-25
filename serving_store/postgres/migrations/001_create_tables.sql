-- ==========================================================================
-- EdNet Serving Store – Initial Schema Migration
-- ==========================================================================
-- This file is auto-executed by the postgres:14 Docker image on first boot
-- via the /docker-entrypoint-initdb.d mount.
-- ==========================================================================

-- ── Recommendations table ─────────────────────────────────────────────────
-- Stores top-K similar users for each student, produced by the processing
-- microservice's similarity computation step.
CREATE TABLE IF NOT EXISTS recommendations (
    id              BIGSERIAL   PRIMARY KEY,
    user_id         TEXT        NOT NULL,
    recommended_user_id TEXT    NOT NULL,
    similarity_score DOUBLE PRECISION NOT NULL,
    rank            INTEGER     NOT NULL,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ── Indexes (Performance) ─────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_recommendations_user_id
    ON recommendations (user_id);

CREATE INDEX IF NOT EXISTS idx_recommendations_user_rank
    ON recommendations (user_id, rank);

-- ── Aggregated student features table ─────────────────────────────────────
-- Stores per-student aggregated features for the API to expose.
CREATE TABLE IF NOT EXISTS student_features (
    id                          BIGSERIAL   PRIMARY KEY,
    user_id                     TEXT        NOT NULL UNIQUE,
    total_interactions          BIGINT,
    correct_count               BIGINT,
    incorrect_count             BIGINT,
    accuracy_rate               DOUBLE PRECISION,
    avg_response_time_ms        DOUBLE PRECISION,
    total_elapsed_time_ms       BIGINT,
    unique_questions_attempted  BIGINT,
    unique_lectures_viewed      BIGINT,
    active_days                 BIGINT,
    created_at                  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_student_features_user_id
    ON student_features (user_id);
