import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.reel_submission import ReelSubmission
from app.worker.error_logging import log_worker_error
from app.worker.extraction import run_knowledge_extraction

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 4
PROCESSING_LEASE = timedelta(minutes=30)


@dataclass(frozen=True)
class ProcessOutcome:
    state: str
    attempt_count: int = 0


async def process_capture(
    capture_id: str,
    session_factory: async_sessionmaker[AsyncSession],
    extractor: Callable[[ReelSubmission], Any] | None = None,
) -> ProcessOutcome:
    capture_uuid = UUID(capture_id)
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        claim = (
            update(ReelSubmission)
            .where(
                ReelSubmission.capture_id == str(capture_uuid),
                ReelSubmission.attempt_count < MAX_ATTEMPTS,
                or_(
                    ReelSubmission.status == "queued",
                    (
                        (ReelSubmission.status == "processing")
                        & (ReelSubmission.lease_expires_at < now)
                    ),
                ),
            )
            .values(
                status="processing",
                job_status="processing",
                attempt_count=ReelSubmission.attempt_count + 1,
                lease_expires_at=now + PROCESSING_LEASE,
            )
            .returning(ReelSubmission)
        )
        claimed = (await session.execute(claim)).scalar_one_or_none()
        await session.commit()

    if claimed is None:
        async with session_factory() as session:
            exhausted = await session.execute(
                update(ReelSubmission)
                .where(
                    ReelSubmission.capture_id == str(capture_uuid),
                    ReelSubmission.attempt_count >= MAX_ATTEMPTS,
                    or_(
                        ReelSubmission.status == "queued",
                        (
                            (ReelSubmission.status == "processing")
                            & (ReelSubmission.lease_expires_at < now)
                        ),
                    ),
                )
                .values(
                    status="failed",
                    job_status="failed",
                    lease_expires_at=None,
                )
            )
            await session.commit()
            if exhausted.rowcount:
                logger.error("Capture exhausted processing attempts: %s", capture_id)
                return ProcessOutcome("failed", MAX_ATTEMPTS)
        return ProcessOutcome("skipped")

    attempt_count = claimed.attempt_count
    try:
        (extractor or run_knowledge_extraction)(claimed)
    except Exception as error:
        terminal = attempt_count >= MAX_ATTEMPTS
        state = "failed" if terminal else "queued"
        async with session_factory() as session:
            update_result = await session.execute(
                update(ReelSubmission)
                .where(
                    ReelSubmission.capture_id == str(capture_uuid),
                    ReelSubmission.status == "processing",
                    ReelSubmission.attempt_count == attempt_count,
                )
                .values(
                    status=state,
                    job_status=state,
                    lease_expires_at=None,
                )
            )
            await session.commit()
        if not update_result.rowcount:
            return ProcessOutcome("lease_lost", attempt_count)
        log_worker_error(
            "extraction_failed_terminal" if terminal else "extraction_failed_retry",
            capture_id,
            error,
        )
        logger.error(
            "Knowledge extraction failed for capture %s on attempt %s",
            capture_id,
            attempt_count,
        )
        return ProcessOutcome("retry" if not terminal else "failed", attempt_count)

    async with session_factory() as session:
        completion = await session.execute(
            update(ReelSubmission)
            .where(
                ReelSubmission.capture_id == str(capture_uuid),
                ReelSubmission.status == "processing",
                ReelSubmission.attempt_count == attempt_count,
            )
            .values(
                status="completed",
                job_status="completed",
                lease_expires_at=None,
            )
        )
        await session.commit()
    if not completion.rowcount:
        return ProcessOutcome("lease_lost", attempt_count)
    return ProcessOutcome("completed", attempt_count)
