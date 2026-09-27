# RecallGraph

FastAPI starter for RecallGraph.

## Run locally

### Run the complete stack in Docker

You only need Docker Desktop and a configured `.env` file. The first command
builds the app image, starts Redis, applies the database migration, and starts
FastAPI and the Celery worker:

```sh
cp env.example .env
# Edit .env and replace the example DATABRICKS_DATABASE_URL with your real URL.
docker compose up --build -d --wait
```

The API is available on your computer at `http://localhost:8000` and
`http://localhost:8000/docs`. Redis stays private to the Compose network; the
API and worker connect to it using the internal Docker hostname `redis:6379`,
which Compose configures automatically. To check Redis, run
`docker compose exec redis redis-cli ping`. The `migrate` service creates the
table if needed and applies the capture job migration before the API or worker
starts.

To see the API, worker, Redis, or migration logs:

```sh
docker compose logs -f api worker redis migrate
```

Worker error details are appended to the persistent `worker_logs` Docker volume.
To view them (after the first worker error):

```sh
docker compose exec worker cat /app/logs/worker-errors.log
```

To stop the stack:

```sh
docker compose down
```

The Celery worker runs with a maximum concurrency of two tasks. For a local
smoke test before the real content-bundle integration exists, set
`WORKER_EXTRACTION_MODE=mock` in `.env` before starting the stack. Keep database
and provider credentials in `.env`; never commit them.

### Environment variables

- `DATABRICKS_DATABASE_URL` (required): PostgreSQL connection URL for the
  `recallgraph` database; include `sslmode=require`.
- `DATABASE_URL` (optional fallback): used only when
  `DATABRICKS_DATABASE_URL` is unset.
- `REDIS_URL` (optional): Celery broker URL; Compose overrides it inside the
  containers to `redis://redis:6379/0`. When running the API/worker directly on
  your host, use `redis://localhost:6379/0`.
- `WORKER_ERROR_LOG` (optional): append-only local file for safe worker error
  diagnostics; defaults to `worker-errors.log`.
- `WORKER_EXTRACTION_MODE` (optional): `mock` runs a harmless mock extractor
  that logs the received capture ID without persisting output; defaults to
  `live`, which currently requires the reel content-bundle preparation stage.
- `GEMINI_API_KEY` (optional): required by the existing standalone Gemini
  knowledge-extraction client when a prepared content bundle is available.
- `SQLALCHEMY_ECHO` (optional, defaults to `false`): set to `true` to log SQL
  statements.
- `DB_DISABLE_PREPARED_STATEMENTS` (optional, defaults to `false`): set to
  `true` to disable asyncpg's prepared-statement cache.

The API docs are available at `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /health` checks that the API is running.
- `POST /api/v1/reels/submit` accepts a user-triggered Instagram Reel capture request.
- `GET /api/v1/reels/status/{capture_id}` returns the database-backed status,
  including `requested_at` and `updated_at`.

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

The API validates the Reel URL, saves a queued capture, then sends a Celery
message containing only its `capture_id`. It returns HTTP `202` without waiting
for worker execution. If Redis is temporarily unavailable after the database
commit, the row stays queued; the recovery command below can re-enqueue it.
Duplicate Reel URLs return the existing submission and do not create another
capture. The database unique index and conditional worker claim protect against
duplicate requests and Celery deliveries.

### Job-state migration

Apply [20260926_add_capture_job_state.sql](./migrations/20260926_add_capture_job_state.sql)
to the configured PostgreSQL database. `docker compose up` runs this migration
automatically in its one-shot `migrate` service before starting the API/worker.
If you run the app directly on your host, apply it manually. The migration
preserves `requested_at` as the initial submitted timestamp, adds a
server-maintained `updated_at`, and removes the obsolete result/error/start/
created columns. For a plain PostgreSQL URL, run:

```sh
psql "$DATABRICKS_DATABASE_URL" -f migrations/20260926_add_capture_job_state.sql
```

### Worker behavior and recovery

Workers atomically claim eligible `queued` captures, set a 30-minute processing
lease, and release the transaction before calling the extraction service.
Transient extraction failures are retried up to four total attempts with
exponential backoff capped at five minutes. Captures become `failed` after the
last attempt; safe error diagnostics are appended locally to `worker-errors.log`
(or the path set with `WORKER_ERROR_LOG`), not persisted in PostgreSQL.
Extraction output is not persisted. Redis/Celery results are ignored;
PostgreSQL stores capture status and timestamps only.

If you run the worker directly on your host and it crashes, restart it and run
the reconciliation command to re-enqueue queued captures and processing
captures whose lease has expired:

```sh
python -m app.worker.reconcile --limit 100
```

The worker also runs reconciliation automatically when it starts (up to 10,000
recoverable captures per startup), so rows left `queued` in PostgreSQL are
re-enqueued after a worker restart.

To verify that a capture reaches the extraction function before the real
content-bundle integration exists, set this in `.env`:

```env
WORKER_EXTRACTION_MODE=mock
```

Restart the worker and watch its logs for `Mock knowledge extraction received
capture_id=...`. Captures processed in mock mode transition to `completed`;
the mock output itself is not saved. Unset it or restore `live` when the actual
extraction integration is ready.

Verify a capture by polling the status endpoint using the `capture_id` returned
by `/submit`:

```sh
curl http://127.0.0.1:8000/api/v1/reels/status/<capture_id>
```

The repository has a Gemini client for an already-prepared `ContentBundle`, but
the backend currently receives only a Reel URL/caption and has no Reel download
or content-bundle preparation stage. Accordingly, the worker calls the
replaceable `run_knowledge_extraction(capture)` boundary; until that upstream
preparation is connected, its explicit configuration error is retried and
eventually reflected by the `failed` status and local worker error log. No
knowledge result or error message is stored in PostgreSQL.
The extraction schema and prompt remain unchanged.

## Databricks PostgreSQL database

Create or select the `recallgraph` database in Databricks PostgreSQL, then set
`DATABRICKS_DATABASE_URL` to its connection URL. The database itself must
already exist; on startup, the app creates the `submissions` table and its
base source/reconciliation indexes if they are missing, then verifies that the
table and indexes are present. The separate job-state migration above is
required for an existing database.
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
