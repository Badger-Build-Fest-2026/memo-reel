CREATE TABLE IF NOT EXISTS capture_knowledge (
    capture_id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    obsidian_url TEXT,
    category VARCHAR(128) NOT NULL,
    knowledge_json JSONB NOT NULL
);
