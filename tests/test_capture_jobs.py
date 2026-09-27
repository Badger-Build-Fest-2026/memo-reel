import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import dialect

from app.api.v1.endpoints import reels as reel_endpoints
from app.api.v1.endpoints.capture_status import get_capture_status
from app.db.session import get_db
from app.models.reel_submission import ReelSubmission
from app.worker.celery_app import celery_app
from app.worker.error_logging import log_worker_error
from app.worker import extraction
from app.worker.extraction import run_knowledge_extraction
from app.worker.processing import MAX_ATTEMPTS, process_capture
from app.worker.startup import enqueue_database_backlog
from app.services.video_download import download_reel_video
from app.worker.tasks import (
    MAX_BACKOFF_SECONDS,
    process_capture_task,
    retry_delay,
)


class ApiSession:
    def __init__(self):
        self.submission = None
        self.committed = False

    async def scalar(self, _statement):
        return None

    def add(self, submission):
        self.submission = submission

    async def commit(self):
        self.committed = True

    async def refresh(self, _submission):
        self.submission.updated_at = datetime.now(timezone.utc)


def test_submit_persists_queued_and_enqueues_only_capture_id(monkeypatch):
    session = ApiSession()
    enqueued = []
    monkeypatch.setattr(
        reel_endpoints.process_capture_task,
        "delay",
        lambda *args: enqueued.append(args),
    )
    app = FastAPI()
    app.include_router(reel_endpoints.router, prefix="/api/v1/reels")

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    capture_id = str(uuid4())

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/v1/reels/submit",
                json={
                    "user_id": "user-1",
                    "account_name": "example",
                    "source_url": "https://www.instagram.com/reel/AbC123/",
                    "hashtags": "#demo",
                    "caption": "caption",
                    "requested_at": "2026-09-26T12:00:00Z",
                },
            )

    response = asyncio.run(request())
    assert response.status_code == 202
    capture_id = response.json()["capture_id"]
    assert UUID(capture_id)
    assert session.committed
    assert session.submission.capture_id == capture_id
    assert session.submission.status == "queued"
    assert session.submission.job_status == "queued"
    assert enqueued == [(capture_id,)]


class ProcessingDatabase:
    def __init__(self, status="queued", attempt_count=0, lease_expires_at=None):
        self.capture_id = str(uuid4())
        self.status = status
        self.attempt_count = attempt_count
        self.lease_expires_at = lease_expires_at

    def session_factory(self):
        return ProcessingSession(self)


class ProcessingSession:
    def __init__(self, database):
        self.database = database

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, statement):
        values = {
            key.key: value.value if hasattr(value, "value") else None
            for key, value in statement._values.items()
        }
        database = self.database
        if str(statement.compile().params.get("capture_id_1")) != database.capture_id:
            return FakeResult(None)
        now = datetime.now(timezone.utc)
        if values.get("status") == "processing":
            eligible = database.status == "queued" or (
                database.status == "processing"
                and database.lease_expires_at is not None
                and database.lease_expires_at < now
            )
            if eligible and database.attempt_count < MAX_ATTEMPTS:
                database.status = "processing"
                database.attempt_count += 1
                database.lease_expires_at = now + timedelta(minutes=30)
                return FakeResult(
                    SimpleNamespace(
                        capture_id=database.capture_id,
                        status=database.status,
                        job_status=database.status,
                        attempt_count=database.attempt_count,
                    )
                )
            return FakeResult(None)

        if values.get("status") == "completed":
            if database.status == "processing":
                database.status = "completed"
                database.lease_expires_at = None
                return FakeResult(rowcount=1)
            return FakeResult(rowcount=0)

        next_status = values.get("status")
        if (
            next_status == "failed"
            and database.status in ("queued", "processing")
            and not (
                database.status == "processing"
                and database.attempt_count < MAX_ATTEMPTS
                and database.lease_expires_at is not None
                and database.lease_expires_at >= now
            )
        ):
            database.status = "failed"
            database.lease_expires_at = None
            return FakeResult(rowcount=1)
        if (
            next_status in ("queued", "failed")
            and database.status == "processing"
            and not (
                next_status == "failed"
                and database.attempt_count < MAX_ATTEMPTS
                and database.lease_expires_at is not None
                and database.lease_expires_at >= now
            )
        ):
            database.status = next_status
            database.lease_expires_at = None
            return FakeResult(rowcount=1)
        return FakeResult(rowcount=0)

    async def commit(self):
        pass


class FakeResult:
    def __init__(self, row=None, rowcount=0):
        self.row = row
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self.row


def test_worker_transitions_queued_to_processing_to_completed():
    database = ProcessingDatabase()

    def extract(capture):
        assert capture.status == "processing"
        assert capture.job_status == "processing"
        return {"topic": "sample"}

    outcome = asyncio.run(
        process_capture(
            database.capture_id,
            database.session_factory,
            extract,
        )
    )
    assert outcome.state == "completed"
    assert database.status == "completed"
    assert database.attempt_count == 1
    assert database.lease_expires_at is None


def test_worker_retries_then_marks_capture_failed():
    database = ProcessingDatabase()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        outcome = asyncio.run(
            process_capture(
                database.capture_id,
                database.session_factory,
                lambda _capture: (_ for _ in ()).throw(
                    ValueError("sensitive provider response")
                ),
            )
        )
        assert outcome.state == ("failed" if attempt == MAX_ATTEMPTS else "retry")
        assert database.status == ("failed" if attempt == MAX_ATTEMPTS else "queued")
    assert database.attempt_count == MAX_ATTEMPTS


def test_completed_duplicate_delivery_is_skipped():
    database = ProcessingDatabase(status="completed")
    invoked = []
    outcome = asyncio.run(
        process_capture(
            database.capture_id,
            database.session_factory,
            lambda _capture: invoked.append(True) or {},
        )
    )
    assert outcome.state == "skipped"
    assert not invoked
    assert database.status == "completed"


def test_duplicate_delivery_does_not_claim_an_active_lease():
    database = ProcessingDatabase(
        status="processing",
        attempt_count=1,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    invoked = []
    outcome = asyncio.run(
        process_capture(
            database.capture_id,
            database.session_factory,
            lambda _capture: invoked.append(True) or {},
        )
    )
    assert outcome.state == "skipped"
    assert not invoked
    assert database.status == "processing"
    assert database.attempt_count == 1


def test_status_response_returns_database_status_and_timestamps_only():
    capture_id = uuid4()
    submission = SimpleNamespace(
        status="completed",
        capture_id=str(capture_id),
        user_id="user-1",
        job_status="completed",
        source_url="https://www.instagram.com/reel/AbC123/",
        requested_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    class StatusSession:
        async def get(self, _model, requested_id):
            assert requested_id == str(capture_id)
            return submission

    response = asyncio.run(get_capture_status(capture_id, StatusSession()))
    assert response.status == "completed"
    assert response.updated_at == submission.updated_at
    assert not hasattr(response, "result")
    assert not hasattr(response, "error")


def test_schema_uses_requested_and_automatically_updated_timestamps():
    columns = set(ReelSubmission.__table__.columns.keys())
    assert {"requested_at", "updated_at"} <= columns
    assert not {
        "result",
        "last_error",
        "processing_started_at",
        "created_at",
    } & columns
    assert ReelSubmission.__table__.c.updated_at.onupdate is not None

    sql = str(
        update(ReelSubmission)
        .values(status="completed")
        .compile(dialect=dialect())
    )
    assert "updated_at=now()" in sql


def test_worker_errors_append_locally_without_exception_message(tmp_path, monkeypatch):
    log_path = tmp_path / "worker-errors.log"
    monkeypatch.setenv("WORKER_ERROR_LOG", str(log_path))
    error = ValueError("provider returned private request content")

    log_worker_error("extraction_failed_retry", str(uuid4()), error)
    log_worker_error("extraction_failed_terminal", str(uuid4()), error)

    contents = log_path.read_text()
    assert contents.count("ValueError") == 2
    assert "private request content" not in contents
    assert "extraction_failed_retry" in contents
    assert "extraction_failed_terminal" in contents


def test_mock_extractor_receives_capture_and_logs_its_id(monkeypatch, caplog):
    capture_id = str(uuid4())
    capture = SimpleNamespace(capture_id=capture_id)
    monkeypatch.setenv("WORKER_EXTRACTION_MODE", "mock")
    caplog.set_level(logging.INFO, logger="app.worker.extraction")

    result = asyncio.run(run_knowledge_extraction(capture))

    assert result == {"mock": True, "capture_id": capture_id}
    assert capture_id in caplog.text


def test_video_downloader_saves_capture_scoped_video(tmp_path, monkeypatch):
    capture_id = str(uuid4())
    downloaded = tmp_path / f"{capture_id}.mp4"
    monkeypatch.delenv("INSTAGRAM_COOKIES_FILE", raising=False)

    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def extract_info(self, _url, download):
            assert download is True
            output_path = Path(
                self.options["outtmpl"].replace("%(ext)s", "mp4")
            )
            output_path.write_bytes(b"fake video")
            return {"filepath": str(output_path)}

    fake_module = ModuleType("yt_dlp")
    fake_module.YoutubeDL = FakeYoutubeDL
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)

    result = download_reel_video(
        "https://www.instagram.com/reel/AbC123/",
        capture_id,
        str(tmp_path),
    )

    assert result == downloaded.resolve()
    assert result.read_bytes() == b"fake video"


def test_live_extractor_downloads_runs_pipeline_and_saves_json_locally(
    tmp_path,
    monkeypatch,
):
    capture_id = str(uuid4())
    capture = SimpleNamespace(
        capture_id=capture_id,
        source_url="https://www.instagram.com/reel/AbC123/",
        caption="caption",
        requested_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    called = {}

    monkeypatch.setenv("WORKER_EXTRACTION_MODE", "live")
    monkeypatch.setenv("PIPELINE_MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.delenv("INSTAGRAM_COOKIES_FILE", raising=False)
    def fake_download(source_url, capture_id, output_dir):
        called["download"] = (source_url, capture_id, output_dir)
        return video

    monkeypatch.setattr(extraction, "download_reel_video", fake_download)

    async def fake_process_reel(**kwargs):
        called["pipeline"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(extraction, "run_pipeline", fake_process_reel)

    def fake_save_knowledge(_knowledge, output_dir):
        output_path = Path(output_dir) / "knowledge.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('{"saved": true}')
        called["output_dir"] = output_dir
        return {"json_path": str(output_path), "jsonl_path": None}

    monkeypatch.setattr(extraction, "save_knowledge", fake_save_knowledge)

    result = asyncio.run(run_knowledge_extraction(capture))

    assert called["download"] == (
        capture.source_url,
        capture_id,
        str((tmp_path / "media" / "videos").resolve()),
    )
    assert called["pipeline"]["video_path"] == str(video)
    assert called["pipeline"]["reel_url"] == capture.source_url
    assert called["pipeline"]["caption"] == "caption"
    assert called["pipeline"]["reel_id"] == capture_id
    assert Path(result["json_path"]).read_text() == '{"saved": true}'


def test_worker_ready_reconciles_queued_database_rows(monkeypatch):
    scheduled_limits = []

    async def fake_reconcile():
        scheduled_limits.append("ran")
        return 3

    monkeypatch.setattr(
        "app.worker.startup._reconcile_and_dispose",
        fake_reconcile,
    )

    enqueue_database_backlog(sender="test-worker")

    assert scheduled_limits == ["ran"]


def test_worker_configuration_caps_concurrency_at_two_with_json():
    assert celery_app.conf.worker_concurrency == 2
    assert celery_app.conf.worker_pool == "threads"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.task_ignore_result
    assert not celery_app.conf.result_backend
    assert "app.worker.tasks" in celery_app.conf.imports
    assert "app.worker.startup" in celery_app.conf.imports
    celery_app.loader.import_default_modules()
    assert (
        celery_app.tasks["app.worker.tasks.process_capture"].name
        == process_capture_task.name
    )
    assert [retry_delay(attempt) for attempt in range(1, 5)] == [1, 2, 4, 8]
    assert retry_delay(100) == MAX_BACKOFF_SECONDS
