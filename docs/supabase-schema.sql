-- =============================================================================
-- LemonCheck — Supabase Database Schema
-- =============================================================================
--
-- Run this in the Supabase SQL Editor (dashboard → SQL Editor → New Query).
-- Safe to run multiple times — uses IF NOT EXISTS and CREATE OR REPLACE.
--
-- Tables:
--   user_usage  — tracks monthly analysis count per authenticated user
--   analyses    — archives full DealReport results with metadata
--
-- Row Level Security (RLS) is enabled on both tables.
-- Users can only read/write their own rows.
-- =============================================================================


-- ── Extensions ────────────────────────────────────────────────────────────────
-- pgcrypto provides gen_random_uuid() for UUID primary keys
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- =============================================================================
-- Table: user_usage
--
-- Tracks how many analyses each user has run in a given calendar month.
-- Used by the usage gate to enforce the 5 analyses/month free tier.
--
-- month format: 'YYYY-MM' (e.g., '2025-01')
-- Upserted (not inserted) on each analysis — see usage_tracker.py.
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_usage (
    user_id        UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    analysis_count INT         NOT NULL DEFAULT 0 CHECK (analysis_count >= 0),
    month          TEXT        NOT NULL CHECK (month ~ '^\d{4}-\d{2}$'),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One row per user per month
    PRIMARY KEY (user_id, month)
);

-- Update updated_at automatically on any row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_usage_updated_at ON user_usage;
CREATE TRIGGER user_usage_updated_at
    BEFORE UPDATE ON user_usage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Index: fast lookup of a user's current month usage (hot path on every /analyze call)
CREATE INDEX IF NOT EXISTS idx_user_usage_lookup
    ON user_usage (user_id, month);

-- Row Level Security
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;

-- Users can only see and modify their own usage rows
CREATE POLICY "Users can read own usage"
    ON user_usage FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own usage"
    ON user_usage FOR UPDATE
    USING (auth.uid() = user_id);

-- Backend service role bypasses RLS (needed for increment_usage in usage_tracker.py)
-- No policy needed — service role always bypasses RLS by design in Supabase.


-- =============================================================================
-- Table: analyses
--
-- Archives every completed DealReport with its input and metadata.
-- Enables:
--   - Users to retrieve past analyses
--   - Deduplication (cache lookup by listing_url hash)
--   - Accuracy auditing via scripts/check_accuracy.py
--
-- result_json stores the full DealReport as JSONB for flexible querying
-- (e.g., find all analyses where grade = 'F', or price_delta > 2000).
-- =============================================================================
CREATE TABLE IF NOT EXISTS analyses (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID        REFERENCES auth.users(id) ON DELETE SET NULL,
    listing_url  TEXT,
    vin          TEXT,
    result_json  JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- At least one of listing_url or vin must be present
    CONSTRAINT must_have_input CHECK (
        listing_url IS NOT NULL OR vin IS NOT NULL
    )
);

-- Index: user's analysis history (for a future "my analyses" page)
CREATE INDEX IF NOT EXISTS idx_analyses_user
    ON analyses (user_id, created_at DESC);

-- Index: deduplication cache — find existing analyses for the same URL
CREATE INDEX IF NOT EXISTS idx_analyses_url
    ON analyses (listing_url)
    WHERE listing_url IS NOT NULL;

-- Index: JSONB index on grade for analytics queries
CREATE INDEX IF NOT EXISTS idx_analyses_grade
    ON analyses USING GIN ((result_json -> 'grade'));

-- Row Level Security
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

-- Users can only read their own analyses
CREATE POLICY "Users can read own analyses"
    ON analyses FOR SELECT
    USING (auth.uid() = user_id);

-- Users can insert their own analyses (user_id must match)
CREATE POLICY "Users can insert own analyses"
    ON analyses FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Anonymous analyses (demo mode) are not readable by regular users
-- The service role (backend) handles all demo/anonymous writes.


-- =============================================================================
-- Verification queries — run these after applying the schema to confirm setup
-- =============================================================================
--
-- SELECT table_name, row_security FROM information_schema.tables
--   WHERE table_schema = 'public';
--
-- SELECT tablename, policyname FROM pg_policies
--   WHERE schemaname = 'public';
--
-- SELECT indexname FROM pg_indexes
--   WHERE schemaname = 'public';
