-- =============================================================================
-- Supabase PostgreSQL Schema Migration
-- Enterprise Compliance AI Platform
-- Run this in Supabase > SQL Editor if audit_reports table needs to be created
-- or altered to match the current SQLAlchemy models.
-- =============================================================================

-- Create the audit_reports table (idempotent)
CREATE TABLE IF NOT EXISTS audit_reports (
    id               SERIAL PRIMARY KEY,
    risk             VARCHAR(20)  NOT NULL,
    compliance_score INTEGER      NOT NULL DEFAULT 0,
    violation_count  INTEGER      NOT NULL DEFAULT 0,
    issues           TEXT         NOT NULL DEFAULT '[]',
    recommendations  TEXT         NOT NULL DEFAULT '[]',
    audit_timestamp  VARCHAR(30)  NOT NULL DEFAULT '',
    auditor          VARCHAR(100) NOT NULL DEFAULT 'Compliance AI Auditor',
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_reports_risk
    ON audit_reports (risk);

CREATE INDEX IF NOT EXISTS idx_audit_reports_compliance_score
    ON audit_reports (compliance_score);

CREATE INDEX IF NOT EXISTS idx_audit_reports_audit_timestamp
    ON audit_reports (audit_timestamp);

CREATE INDEX IF NOT EXISTS idx_audit_reports_created_at
    ON audit_reports (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_risk_timestamp
    ON audit_reports (risk, audit_timestamp);

-- =============================================================================
-- Alter existing table if upgrading from an older schema
-- Run individual statements below only if you already have the table.
-- =============================================================================

-- If `issues` column exists as JSON type, convert to TEXT:
-- ALTER TABLE audit_reports ALTER COLUMN issues TYPE TEXT USING issues::TEXT;

-- If `recommendations` column exists as JSON type, convert to TEXT:
-- ALTER TABLE audit_reports ALTER COLUMN recommendations TYPE TEXT USING recommendations::TEXT;

-- If `created_at` is missing:
-- ALTER TABLE audit_reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- If `violation_count` is missing:
-- ALTER TABLE audit_reports ADD COLUMN IF NOT EXISTS violation_count INTEGER NOT NULL DEFAULT 0;

-- Verify schema
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'audit_reports'
ORDER BY ordinal_position;
