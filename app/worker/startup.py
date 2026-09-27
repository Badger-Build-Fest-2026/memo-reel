import asyncio
import logging

from celery.signals import worker_ready

from app.db.session import get_engine
from app.worker.error_logging import log_worker_error
from app.worker.reconcile import enqueue_recoverable_captures

logger = logging.getLogger(__name__)
STARTUP_RECONCILE_LIMIT = 10000


async def _reconcile_and_dispose() -> int:
    engine = get_engine()
    try:
        return await enqueue_recoverable_captures(limit=STARTUP_RECONCILE_LIMIT)
    finally:
        await engine.dispose()


@worker_ready.connect
def enqueue_database_backlog(sender=None, **_kwargs) -> None:
    try:
        queued_count = asyncio.run(_reconcile_and_dispose())
    except Exception as error:
        log_worker_error("startup_reconciliation_failed", "batch", error)
        logger.exception("Could not enqueue recoverable captures at worker startup")
        return

    logger.info(
        "Startup reconciliation enqueued %s recoverable capture(s) for worker %s",
        queued_count,
        sender,
    )
