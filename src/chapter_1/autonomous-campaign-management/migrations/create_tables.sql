-- ============================================================================
-- Database Schema: Autonomous Campaign Management
-- Target: Aurora PostgreSQL with TimescaleDB extension
-- ============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- Campaign Briefs
-- ============================================================================

CREATE TABLE campaign_briefs (
    brief_id        VARCHAR(64) PRIMARY KEY DEFAULT 'brief-' || substr(uuid_generate_v4()::text, 1, 8),
    raw_text        TEXT NOT NULL,
    budget_total    NUMERIC(18, 4) NOT NULL,
    target_cpa      NUMERIC(18, 4) NOT NULL,
    audience_description TEXT,
    platforms       JSONB DEFAULT '["meta", "google", "tiktok", "amazon"]',
    sentiment_threshold DOUBLE PRECISION DEFAULT 0.75,
    constraints     JSONB DEFAULT '{}',
    parsed_parameters JSONB,
    is_valid        BOOLEAN DEFAULT TRUE,
    validation_errors JSONB,
    submitted_by    VARCHAR(128),
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Campaign States (core lifecycle table)
-- ============================================================================

CREATE TYPE campaign_status AS ENUM (
    'DRAFT', 'APPROVED', 'LAUNCHING', 'ACTIVE', 'OPTIMIZING', 'PAUSED', 'COMPLETED'
);

CREATE TABLE campaign_states (
    campaign_id     VARCHAR(64) PRIMARY KEY DEFAULT 'camp-' || substr(uuid_generate_v4()::text, 1, 8),
    brief_id        VARCHAR(64) REFERENCES campaign_briefs(brief_id),
    status          campaign_status DEFAULT 'DRAFT' NOT NULL,

    -- Budget
    budget_total    NUMERIC(18, 4) NOT NULL,
    budget_spent    NUMERIC(18, 4) DEFAULT 0,
    budget_remaining NUMERIC(18, 4),
    daily_budget    NUMERIC(18, 4),

    -- Targets
    target_cpa      NUMERIC(18, 4) NOT NULL,
    current_cpa     NUMERIC(18, 4),
    target_roas     DOUBLE PRECISION,
    current_roas    DOUBLE PRECISION,

    -- Sentiment
    sentiment_threshold DOUBLE PRECISION DEFAULT 0.75,
    current_sentiment   DOUBLE PRECISION,

    -- Schedule
    start_date      TIMESTAMPTZ,
    end_date        TIMESTAMPTZ,
    flight_days     INTEGER,

    -- Configuration
    platform_configs JSONB,
    initial_allocation JSONB,

    -- Metadata
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    approved_at     TIMESTAMPTZ,
    approved_by     VARCHAR(128),
    launched_at     TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_campaign_status ON campaign_states(status);
CREATE INDEX idx_campaign_dates ON campaign_states(created_at, status);

-- ============================================================================
-- Platform Campaigns (per-platform state)
-- ============================================================================

CREATE TABLE platform_campaigns (
    platform_campaign_id VARCHAR(64) PRIMARY KEY DEFAULT 'pc-' || substr(uuid_generate_v4()::text, 1, 8),
    campaign_id     VARCHAR(64) REFERENCES campaign_states(campaign_id) NOT NULL,
    platform        VARCHAR(32) NOT NULL,

    -- External IDs
    external_campaign_id VARCHAR(256),
    external_ad_group_ids JSONB,

    -- Config
    platform_config JSONB,
    audience_targeting JSONB,
    bid_strategy    VARCHAR(64),
    current_bid     NUMERIC(18, 4),

    -- Budget
    allocated_budget NUMERIC(18, 4),
    daily_budget    NUMERIC(18, 4),
    spent           NUMERIC(18, 4) DEFAULT 0,

    -- Performance (latest)
    current_cpa     NUMERIC(18, 4),
    current_roas    DOUBLE PRECISION,
    current_ctr     DOUBLE PRECISION,
    impressions_total BIGINT DEFAULT 0,
    conversions_total BIGINT DEFAULT 0,

    -- Status
    platform_status VARCHAR(32) DEFAULT 'PENDING',
    last_sync_at    TIMESTAMPTZ,
    last_error      VARCHAR(512),

    -- Metadata
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_platform_campaign ON platform_campaigns(campaign_id, platform);
CREATE INDEX idx_platform_status ON platform_campaigns(platform, platform_status);

-- ============================================================================
-- Guardrails
-- ============================================================================

CREATE TABLE guardrails (
    guardrail_id    VARCHAR(64) PRIMARY KEY DEFAULT 'gr-' || substr(uuid_generate_v4()::text, 1, 8),
    campaign_id     VARCHAR(64) NOT NULL,
    guardrail_type  VARCHAR(32) NOT NULL,
    description     VARCHAR(256),

    threshold_value NUMERIC(18, 4),
    threshold_pct   DOUBLE PRECISION,
    threshold_duration_hours DOUBLE PRECISION,

    action_on_breach VARCHAR(32) DEFAULT 'block',
    is_hard_limit   BOOLEAN DEFAULT TRUE,
    enabled         BOOLEAN DEFAULT TRUE,

    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      VARCHAR(128)
);

CREATE INDEX idx_guardrail_campaign ON guardrails(campaign_id, guardrail_type);

-- ============================================================================
-- Audit Log (APPEND-ONLY — no UPDATE or DELETE allowed)
-- ============================================================================

CREATE TABLE audit_log (
    entry_id        VARCHAR(64) PRIMARY KEY DEFAULT 'aud-' || substr(uuid_generate_v4()::text, 1, 8),
    campaign_id     VARCHAR(64) NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    agent           VARCHAR(64) NOT NULL,
    action_type     VARCHAR(32) NOT NULL,

    pre_state       JSONB,
    post_state      JSONB,

    reasoning       TEXT,
    metrics_at_decision JSONB,
    confidence_score VARCHAR(8),

    guardrail_check_passed BOOLEAN DEFAULT TRUE,
    guardrail_details JSONB,

    reversible      BOOLEAN DEFAULT TRUE,
    reversed        BOOLEAN DEFAULT FALSE,
    reversed_at     TIMESTAMPTZ,
    reversed_by     VARCHAR(128),

    correlation_id  VARCHAR(64),
    parent_entry_id VARCHAR(64)
);

CREATE INDEX idx_audit_campaign_time ON audit_log(campaign_id, timestamp);
CREATE INDEX idx_audit_agent ON audit_log(agent, timestamp);
CREATE INDEX idx_audit_action_type ON audit_log(action_type, timestamp);
CREATE INDEX idx_audit_correlation ON audit_log(correlation_id);

-- Prevent updates/deletes on audit_log (immutable)
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log is immutable. Updates and deletes are not allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW
    WHEN (OLD.reversed IS NOT DISTINCT FROM NEW.reversed)
    EXECUTE FUNCTION prevent_audit_modification();

CREATE TRIGGER audit_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_modification();

-- ============================================================================
-- Performance Metrics (TimescaleDB hypertable)
-- ============================================================================

CREATE TABLE fact_ad_performance_hourly (
    event_hour      TIMESTAMPTZ NOT NULL,
    platform        VARCHAR(32) NOT NULL,
    account_id      VARCHAR(128) NOT NULL,
    campaign_id     VARCHAR(128) NOT NULL,
    ad_group_id     VARCHAR(128),
    ad_id           VARCHAR(128) NOT NULL,
    creative_id     VARCHAR(128),

    impressions     BIGINT DEFAULT 0,
    clicks          BIGINT DEFAULT 0,
    spend           NUMERIC(18, 4) DEFAULT 0,
    conversions     BIGINT DEFAULT 0,
    conversion_value NUMERIC(18, 4) DEFAULT 0,

    ctr             DOUBLE PRECISION,
    cpc             NUMERIC(18, 6),
    cpm             NUMERIC(18, 6),
    cpa             NUMERIC(18, 6),
    roas            DOUBLE PRECISION,

    source_attribution_type VARCHAR(64),
    ingestion_ts    TIMESTAMPTZ DEFAULT NOW(),
    source_file     VARCHAR(512)
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('fact_ad_performance_hourly', 'event_hour');

CREATE INDEX idx_perf_campaign_hour ON fact_ad_performance_hourly(campaign_id, event_hour DESC);
CREATE INDEX idx_perf_platform_hour ON fact_ad_performance_hourly(platform, event_hour DESC);
CREATE INDEX idx_perf_creative_hour ON fact_ad_performance_hourly(creative_id, event_hour DESC);

-- ============================================================================
-- Pacing Snapshots
-- ============================================================================

CREATE TABLE pacing_snapshots (
    snapshot_id     VARCHAR(64) PRIMARY KEY DEFAULT 'pace-' || substr(uuid_generate_v4()::text, 1, 8),
    campaign_id     VARCHAR(128) NOT NULL,
    platform        VARCHAR(32),
    snapshot_time   TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    expected_spend  NUMERIC(18, 4),
    actual_spend    NUMERIC(18, 4),
    pacing_ratio    DOUBLE PRECISION,
    projected_exhaustion_date TIMESTAMPTZ,

    pacing_status   VARCHAR(16)
);

CREATE INDEX idx_pacing_campaign_time ON pacing_snapshots(campaign_id, snapshot_time DESC);
