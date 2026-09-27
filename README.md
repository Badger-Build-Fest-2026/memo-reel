# Memo Reel

## Agent configuration

The GraphRAG agent (`agent/langgraph_agent.py`) resolves a Gemini model id in this
order and tries each one before giving up:

1. `GEMINI_MODEL` (explicit override)
2. `DEFAULT_GEMINI_MODEL` -> `gemini-flash-latest`
3. `FALLBACK_GEMINI_MODEL` -> `gemini-flash-lite-latest` (separate free-tier quota bucket)

> `gemini-1.5-flash` and `gemini-2.5-flash` are closed for this key and return
> `404 NOT_FOUND`. Do not pin them. A failed LLM call is never swallowed: it is logged
> to stderr, recorded in `get_last_agent_error()`, and the reply is prefixed with a
> visible "Degraded mode" banner naming the failing model.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Credentials; if unset the agent runs on the deterministic graph engine. |
| `GEMINI_MODEL` | Pin the primary model id. |
| `DATABRICKS_DATABASE_URL` | Live Lakebase source; falls back to `data/dummy_reels.jsonl`. |
| `REELMIND_OFFLINE=1` | Force deterministic graph-engine answers (tests / CI / quota safety). |
| `REELMIND_LIVE=1` | `scripts/verify_agent.py` opt-in to exercise the real Gemini call. |

## Retrieval scoping guarantee

A query that names a subcategory is answered **only** from reels in that subcategory:
`_resolve_subcategory()` maps it to one canonical subcategory and `search_reels`
restricts candidates via `ReelGraphEngine.get_reels_by_subcategory()`. Graph traversal
(`get_connected_topics`) walks the 4-tier graph strictly downward
(Category -> Subcategory -> Concept -> Reel), so sibling branches such as
[[System Design]] and [[Data Science]] never bleed into each other.

## Verification

```bash
python scripts/verify_part1.py                   # Lakebase schema + 4-tier graph topology
python scripts/verify_agent.py                   # agent tools + subcategory isolation (offline by default)
REELMIND_LIVE=1 python scripts/verify_agent.py   # same, against the real Gemini model
python scripts/verify_carousel_ui.py             # headless Streamlit AppTest carousel checks
```

# Memo Reel

FastAPI starter for Memo Reel.

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
`http://localhost:8000/docs`. If port 8000 is already in use, change
`API_PORT` in `.env` (for example, to `8001`). Redis stays private to the Compose network; the
API and worker connect to it using the internal Docker hostname `redis:6379`,
which Compose configures automatically. To check Redis, run
`docker compose exec redis redis-cli ping`. The `migrate` service creates the
table if needed and applies the capture job migration before the API or worker
starts. The API runs Uvicorn with `--reload` and mounts `./app` read-only into
the container, so Python changes under `app/` restart the API automatically.
Worker code changes still require restarting the worker service.

To see the API, worker, Redis, or migration logs:

```sh
docker compose logs -f api worker redis migrate
```

All worker `ERROR`-level log records, including records from third-party
libraries, are appended without timestamps to the persistent `worker_logs`
Docker volume. Sensitive tokens and URL query strings are redacted; captions
and LLM inputs are not logged. To view them:

```sh
docker compose exec worker cat /app/watchlogs/worker-errors.log
```

To stop the stack:

```sh
docker compose down
```

The Celery worker runs with a maximum concurrency of two tasks. Set
`WORKER_EXTRACTION_MODE=mock` in `.env` only for a pipeline smoke test; normal
operation downloads and processes the Reel. Keep database and provider
credentials in `.env`; never commit them.

### Environment variables

- `DATABRICKS_DATABASE_URL` (required): PostgreSQL connection URL for the
  `recallgraph` database; include `sslmode=require`.
- `DATABASE_URL` (optional fallback): used only when
  `DATABRICKS_DATABASE_URL` is unset.
- `REDIS_URL` (optional): Celery broker URL; Compose overrides it inside the
  containers to `redis://redis:6379/0`. When running the API/worker directly on
  your host, use `redis://localhost:6379/0`.
- `API_PORT` (optional): host port exposed by the Compose API service; defaults
  to `8000`.
- `WORKER_ERROR_LOG` (optional): append-only local file for safe worker error
  diagnostics; defaults to `worker-errors.log`.
- `WORKER_EXTRACTION_MODE` (optional): `mock` runs a harmless mock extractor
  that logs the received capture ID without persisting output; defaults to
  `live`, which downloads and processes the Reel.
- `PIPELINE_MEDIA_DIR` (optional): local directory for downloaded videos and
  per-capture output; defaults to `media`. Compose mounts the project `media/`
  directory into the worker at `/app/media`.
- `INSTAGRAM_COOKIES_FILE` (optional): private Netscape-format cookie file for
  Instagram downloads that require a signed-in session. In Docker, place it
  under `media/` so the worker can read it. Never commit this file.
- `GEMINI_API_KEY` (required for live extraction): used by the existing Gemini
  knowledge-extraction client. Add it to `.env` without committing the key.
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

### Database migrations

Compose applies both migrations automatically through its one-shot `migrate`
service before starting the API/worker. If running outside Compose, apply the
job-state migration and the knowledge table migration manually. The first
migration preserves `requested_at` as the initial submitted timestamp, adds a
server-maintained `updated_at`, and removes obsolete columns:

```sh
psql "$DATABRICKS_DATABASE_URL" -f migrations/20260926_add_capture_job_state.sql
psql "$DATABRICKS_DATABASE_URL" -f migrations/20260927_add_capture_knowledge.sql
```

The `capture_knowledge` table stores one row per capture. `capture_id` is its
primary key; `user_id`, `requested_at`, `delivered_at`, `obsidian_url`,
`category`, and `knowledge_json` store the source metadata and the entire JSON
document. `requested_at` comes from the submitted capture timestamp;
`delivered_at` is set by PostgreSQL when the generated result is saved and
refreshed if the same capture is reprocessed.
`obsidian_url` is nullable until present in the JSON. Reprocessing a capture
updates its existing row rather than creating a duplicate. The worker keeps the
local JSON file and does not mark the capture completed unless the database
upsert succeeds.

Confirm the table and inspect a saved result with:

```sql
SELECT capture_id, user_id, requested_at, delivered_at, obsidian_url, category
FROM capture_knowledge
ORDER BY delivered_at DESC
LIMIT 10;
```

### Worker behavior and recovery

Workers atomically claim eligible `queued` captures, set a two-hour processing
lease, and release the transaction before calling the extraction service.
Transient extraction failures are retried up to four total attempts with
exponential backoff capped at five minutes. Captures become `failed` after the
last attempt; sanitized error diagnostics with capture ID, stage, exception
type, and cause summary are appended locally to `worker-errors.log` (or the
path set with `WORKER_ERROR_LOG`), not persisted in PostgreSQL.
Retries reuse a non-empty downloaded video for the capture. If valid final
knowledge JSON was already written, retries reuse it and continue at the
database upsert instead of downloading or rerunning the pipeline. JSON files
are replaced atomically so an interrupted write is not mistaken for a result.
If the LLM stage fails before final JSON exists, successfully completed frame
extraction and transcription are cached under the capture's local pipeline
directory and reused on retry. The LLM request itself is retried because it
did not produce a valid result.
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

To verify scheduling without downloading a Reel or calling Gemini, set this in
`.env`:

```env
WORKER_EXTRACTION_MODE=mock
```

Restart the worker and watch its logs for `Mock knowledge extraction received
capture_id=...`. Captures processed in mock mode transition to `completed`;
the mock output itself is not saved. Restore `live` to run the downloader and
full pipeline.

Verify a capture by polling the status endpoint using the `capture_id` returned
by `/submit`:

```sh
curl http://127.0.0.1:8000/api/v1/reels/status/<capture_id>
```

In live mode the worker downloads the source URL to
`media/videos/<capture_id>.*`, calls the existing `process_reel` pipeline with
the local video and submitted Reel metadata, and saves the generated JSON under
`media/output/<capture_id>/`. These files are visible in the project directory
when running through Docker Compose; the JSON result is not stored in
PostgreSQL.

Instagram may require a signed-in session to download a Reel. If yt-dlp cannot
download a Reel anonymously, provide a private Netscape-format browser cookie
file in `media/instagram-cookies.txt` and set this in `.env`:

```env
INSTAGRAM_COOKIES_FILE=/app/media/instagram-cookies.txt
```

The worker reads cookies locally; they are never included in the Celery
message. Download or pipeline failures follow the configured retries and are
recorded in the local worker error log.

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
