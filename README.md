# RecallGraph

FastAPI starter for RecallGraph.

## Run locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SUPABASE_DATABASE_URL='postgresql+asyncpg://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres'
uvicorn app.main:app --reload
```

The API checks the database connection at startup by running `SELECT 1`. If
`SUPABASE_DATABASE_URL` is missing or Supabase is unreachable, startup fails
before the app accepts requests.

The API docs are available at `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /health` checks that the API is running.
- `POST /api/v1/reels/submit` accepts a user-triggered Instagram Reel capture request.

Example request:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/reels/submit \
	-H 'Content-Type: application/json' \
	-d '{
            "user_id": "user-123",
            "account_name": "example_user",
            "source_url": "https://www.instagram.com/reel/DdjIyezy1Wg/",
            "hashtags": "#travel #food",
            "caption": "A great place to visit",
            "requested_at": "2026-09-26T12:00:00Z"
        }'
```

The API validates the Reel URL, creates a queued capture job, and returns a
`capture_id`.

## Database

Run this in the Supabase SQL Editor before starting the API:

```sql
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
```

Supabase provisions the Postgres database for the project, so you do not need to
run `CREATE DATABASE`. For direct connection, use the `db.<project-ref>.supabase.co`
host on port `5432`. You can paste either Supabase's plain `postgresql://...`
connection string or the SQLAlchemy-style `postgresql+asyncpg://...` URL into
`SUPABASE_DATABASE_URL`; the app converts plain `postgresql://...` URLs to
asyncpg automatically.
