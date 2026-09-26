from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.reel import ReelSubmissionRequest, ReelSubmissionResponse
from app.services.reel_service import submit_reel

router = APIRouter()


@router.post(
    "/submit",
    response_model=ReelSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_reel_submission(
    request: ReelSubmissionRequest,
    db: AsyncSession = Depends(get_db),
) -> ReelSubmissionResponse:
    return await submit_reel(request=request, db=db)
