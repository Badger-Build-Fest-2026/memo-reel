from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.reel_submission import ReelSubmission
from app.services.reel_service import submission_response
from app.schemas.reel import ReelSubmissionResponse

router = APIRouter()


@router.get("/{capture_id}", response_model=ReelSubmissionResponse)
async def get_capture_status(
    capture_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ReelSubmissionResponse:
    submission = await db.get(ReelSubmission, str(capture_id))
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capture not found",
        )
    return submission_response(submission)
