import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.reel import ReelSubmissionRequest, ReelSubmissionResponse
from app.services.reel_service import submit_reel
from app.worker.tasks import process_capture_task

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/submit",
    response_model=ReelSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_reel_submission(
    request: ReelSubmissionRequest,
    db: AsyncSession = Depends(get_db),
) -> ReelSubmissionResponse:
    capture_id = str(uuid.uuid4())
    response = await submit_reel(request=request, capture_id=capture_id, db=db)
    if response.status == "queued":
        try:
            process_capture_task.delay(response.capture_id)
        except Exception:
            logger.error(
                "Could not enqueue capture %s; queued work can be recovered with "
                "python -m app.worker.reconcile",
                response.capture_id,
            )
    return response
