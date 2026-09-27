CREATE TABLE IF NOT EXISTS submissions (
	capture_id UUID PRIMARY KEY,
	user_id VARCHAR(255) NOT NULL,
	account_name VARCHAR(255) NOT NULL,
	source_url VARCHAR(2048) NOT NULL,
	hashtags TEXT NOT NULL DEFAULT '',
	caption TEXT NOT NULL DEFAULT '',
	requested_at TIMESTAMPTZ NOT NULL,
	status VARCHAR(32) NOT NULL DEFAULT 'queued',
	job_status VARCHAR(32) NOT NULL DEFAULT 'queued',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_submissions_source_url
	ON submissions (source_url);
