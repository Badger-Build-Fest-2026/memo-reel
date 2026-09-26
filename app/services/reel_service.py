import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reel_submission import ReelSubmission
from app.schemas.reel import ReelSubmissionRequest, ReelSubmissionResponse


async def submit_reel(
    request: ReelSubmissionRequest,
    db: AsyncSession,
) -> ReelSubmissionResponse:
    submission = ReelSubmission(
        capture_id=str(uuid.uuid4()),
        source_url=request.source_url,
        capture_mode=request.capture_mode.value,
        caption=request.caption,
        requested_at=request.requested_at,
        status="queued",
        job_status="queued",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    return ReelSubmissionResponse(
        status=submission.status,
        capture_id=submission.capture_id,
        job_status=submission.job_status,
        source_url=submission.source_url,
        capture_mode=submission.capture_mode,
        requested_at=submission.requested_at,
    )
