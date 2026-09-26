# RecallGraph

FastAPI starter for RecallGraph.

## Run locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/recallgraph'
uvicorn app.main:app --reload
```

The API checks the database connection at startup by running `SELECT 1`. If
`DATABASE_URL` is missing or Postgres is unreachable, startup fails before the
app accepts requests.

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

The API validates the Reel URL and capture mode, creates a queued capture job,
and returns a `capture_id`.

## Database

Run this in Postgres before starting the API:

```sql
CREATE TABLE IF NOT EXISTS reel_submissions (
	capture_id UUID PRIMARY KEY,
	source_url VARCHAR(2048) NOT NULL,
	capture_mode VARCHAR(64) NOT NULL CHECK (capture_mode IN ('selected_content')),
	caption TEXT NOT NULL DEFAULT '',
	requested_at TIMESTAMPTZ NOT NULL,
	status VARCHAR(32) NOT NULL DEFAULT 'queued',
	job_status VARCHAR(32) NOT NULL DEFAULT 'queued',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_reel_submissions_source_url
	ON reel_submissions (source_url);
```
