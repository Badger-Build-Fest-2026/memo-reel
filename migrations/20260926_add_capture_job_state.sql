ALTER TABLE submissions
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    DROP COLUMN IF EXISTS result,
    DROP COLUMN IF EXISTS last_error,
    DROP COLUMN IF EXISTS processing_started_at,
    DROP COLUMN IF EXISTS created_at;

CREATE INDEX IF NOT EXISTS ix_submissions_job_reconcile
    ON submissions (status, lease_expires_at);
