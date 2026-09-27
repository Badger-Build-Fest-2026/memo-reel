# RecallGraph

FastAPI starter for RecallGraph.

## Run locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABRICKS_DATABASE_URL='postgresql://<user>:<password>@<endpoint>.database.<region>.cloud.databricks.com/recallgraph?sslmode=require'
uvicorn app.main:app --reload
```

The API checks the database connection at startup by running `SELECT 1`. If
`DATABRICKS_DATABASE_URL` is missing or Databricks PostgreSQL is unreachable,
startup fails before the app accepts requests. The connection URL can also use
the generic `DATABASE_URL` variable. Keep the URL in an environment variable
and never commit credentials.

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

## Databricks PostgreSQL database

Create or select the `recallgraph` database in Databricks PostgreSQL, then run
the following SQL in that database before starting the API (the app does not
create the database itself):

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

Set `DATABRICKS_DATABASE_URL` to the Databricks PostgreSQL connection URL with
`recallgraph` as its database path and `sslmode=require`. Both plain
`postgresql://...` and SQLAlchemy-style `postgresql+asyncpg://...` URLs are
supported; the app converts the plain PostgreSQL scheme to asyncpg
automatically.
