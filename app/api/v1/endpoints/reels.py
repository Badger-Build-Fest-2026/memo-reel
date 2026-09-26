from fastapi import APIRouter

from app.schemas.reel import ReelSubmissionRequest, ReelSubmissionResponse
from app.services.reel_service import submit_reel

router = APIRouter()


@router.post("", response_model=ReelSubmissionResponse)
def create_reel_submission(
    request: ReelSubmissionRequest,
) -> ReelSubmissionResponse:
    return submit_reel(request)