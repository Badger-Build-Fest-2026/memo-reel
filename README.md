# RecallGraph

FastAPI starter for RecallGraph.

## Run locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# Edit .env and set DATABRICKS_DATABASE_URL to your actual connection URL.
uvicorn app.main:app --reload
```

The API checks the database connection at startup by running `SELECT 1`. If
`DATABRICKS_DATABASE_URL` is missing or Databricks PostgreSQL is unreachable,
startup fails before the app accepts requests. The connection URL can also use
the generic `DATABASE_URL` variable if `DATABRICKS_DATABASE_URL` is unset.
Keep the URL in `.env` and never commit credentials.

### Environment variables

- `DATABRICKS_DATABASE_URL` (required): PostgreSQL connection URL for the
  `recallgraph` database; include `sslmode=require`.
- `DATABASE_URL` (optional fallback): used only when
  `DATABRICKS_DATABASE_URL` is unset.
- `SQLALCHEMY_ECHO` (optional, defaults to `false`): set to `true` to log SQL
  statements.
- `DB_DISABLE_PREPARED_STATEMENTS` (optional, defaults to `false`): set to
  `true` to disable asyncpg's prepared-statement cache.

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
`capture_id`. It extracts the Reel ID from the URL and checks whether the Reel
was already submitted, regardless of URL query parameters or `/reel/` versus
`/reels/` spelling. Duplicate submissions return the existing submission
response, including its original `capture_id` and current job status, without
creating another capture. A unique database index on the normalized Reel URL
also prevents duplicates from concurrent requests.

## Databricks PostgreSQL database

Create or select the `recallgraph` database in Databricks PostgreSQL, then set
`DATABRICKS_DATABASE_URL` to its connection URL. The database itself must
already exist; on startup, the app creates the `submissions` table and its
`source_url` index if they are missing, then verifies that both are present.
Startup fails with an error if the connection, creation, or verification fails.

After startup, you can confirm the table and index in the connected database:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = current_schema()
  AND table_name = 'submissions';

SELECT indexname
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename = 'submissions'
  AND indexname = 'uq_submissions_source_url';
```

Use the Databricks PostgreSQL connection URL with `recallgraph` as its database
path and `sslmode=require`. Both plain
`postgresql://...` and SQLAlchemy-style `postgresql+asyncpg://...` URLs are
supported; the app converts the plain PostgreSQL scheme to asyncpg
automatically.
