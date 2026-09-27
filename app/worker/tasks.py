import asyncio
import logging
from uuid import UUID

from app.db.session import create_engine
from app.worker.celery_app import celery_app
from app.worker.error_logging import log_worker_error
from app.worker.processing import MAX_ATTEMPTS, ProcessOutcome, process_capture
from sqlalchemy.ext.asyncio import async_sessionmaker

logger = logging.getLogger(__name__)
MAX_RETRIES = MAX_ATTEMPTS - 1
MAX_BACKOFF_SECONDS = 300


def retry_delay(attempt_count: int) -> int:
    return min(2 ** max(attempt_count - 1, 0), MAX_BACKOFF_SECONDS)


async def _process_and_dispose(capture_id: str) -> ProcessOutcome:
    engine = create_engine()
    try:
        session_factory = async_sessionmaker(
            bind=engine,
            autoflush=False,
            expire_on_commit=False,
        )
        return await process_capture(capture_id, session_factory)
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="app.worker.tasks.process_capture",
    max_retries=MAX_RETRIES,
    ignore_result=True,
)
def process_capture_task(task, capture_id: str) -> str:
    UUID(capture_id)
    try:
        outcome = asyncio.run(_process_and_dispose(capture_id))
    except Exception as error:
        log_worker_error(
            "task_processing_failed",
            capture_id,
            error,
            stage="task_execution",
        )
        retries = task.request.retries
        if retries >= MAX_RETRIES:
            logger.error("Capture task exhausted retries for %s", capture_id)
            raise
        logger.error("Capture task will retry after a processing error: %s", capture_id)
        raise task.retry(countdown=retry_delay(retries + 1))

    if outcome.state == "retry":
        raise task.retry(countdown=retry_delay(outcome.attempt_count))
    return outcome.state
