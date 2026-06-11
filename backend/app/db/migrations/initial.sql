-- ============================================================
-- Enterprise Compliance AI Platform — Full Database Migration
-- Run this in Supabase SQL Editor to initialise the schema.
-- Safe to run multiple times (uses IF NOT EXISTS).
-- ============================================================

-- User role enum
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'auditor', 'compliance_officer');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id               SERIAL          PRIMARY KEY,
    email            VARCHAR(255)    NOT NULL UNIQUE,
    full_name        VARCHAR(150)    NOT NULL,
    hashed_password  VARCHAR(255)    NOT NULL,
    role             user_role       NOT NULL DEFAULT 'auditor',
    is_active        BOOLEAN         NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ     NOT NULL DEFAULT now(),
    last_login_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email    ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_role     ON users (role);

-- Audit reports table
CREATE TABLE IF NOT EXISTS audit_reports (
    id                   SERIAL          PRIMARY KEY,
    risk                 VARCHAR(20)     NOT NULL,
    compliance_score     INTEGER         NOT NULL DEFAULT 0,
    violation_count      INTEGER         NOT NULL DEFAULT 0,
    issues               TEXT            NOT NULL DEFAULT '[]',
    recommendations      TEXT            NOT NULL DEFAULT '[]',
    audit_timestamp      VARCHAR(30)     NOT NULL DEFAULT '',
    auditor              VARCHAR(100)    NOT NULL DEFAULT 'Compliance AI Auditor',
    created_by_user_id   INTEGER         REFERENCES users(id) ON DELETE SET NULL,
    created_at           TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_reports_risk           ON audit_reports (risk);
CREATE INDEX IF NOT EXISTS idx_audit_reports_score          ON audit_reports (compliance_score);
CREATE INDEX IF NOT EXISTS idx_audit_reports_timestamp      ON audit_reports (audit_timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_reports_created_at     ON audit_reports (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_reports_user           ON audit_reports (created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_risk_timestamp               ON audit_reports (risk, audit_timestamp);

-- Trigger: auto-update updated_at on users
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();

-- Verify
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name IN ('users', 'audit_reports')
  AND table_schema = 'public'
ORDER BY table_name, ordinal_position;
