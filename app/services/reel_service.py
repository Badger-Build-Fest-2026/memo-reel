import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reel_submission import ReelSubmission
from app.schemas.reel import ReelSubmissionRequest, ReelSubmissionResponse


def submission_response(submission: ReelSubmission) -> ReelSubmissionResponse:
    return ReelSubmissionResponse(
        status=submission.status,
        capture_id=submission.capture_id,
        user_id=submission.user_id,
        job_status=submission.job_status,
        source_url=submission.source_url,
        requested_at=submission.requested_at,
        updated_at=submission.updated_at,
    )


async def submit_reel(
    request: ReelSubmissionRequest,
    capture_id: str,
    db: AsyncSession,
) -> ReelSubmissionResponse:
    canonical_url = f"https://www.instagram.com/reel/{request.reel_id}/"
    existing_submission = await db.scalar(
        select(ReelSubmission).where(ReelSubmission.source_url == canonical_url)
    )
    if existing_submission is not None:
        return submission_response(existing_submission)

    submission = ReelSubmission(
        capture_id=capture_id,
        user_id=request.user_id,
        account_name=request.account_name,
        source_url=request.source_url,
        hashtags=request.hashtags,
        caption=request.caption,
        requested_at=request.requested_at,
        status="queued",
        job_status="queued",
    )
    db.add(submission)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing_submission = await db.scalar(
            select(ReelSubmission).where(ReelSubmission.source_url == canonical_url)
        )
        if existing_submission is not None:
            return submission_response(existing_submission)
        raise
    await db.refresh(submission)

    return submission_response(submission)
