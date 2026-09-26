from app.schemas.reel import ReelSubmissionRequest, ReelSubmissionResponse


def submit_reel(request: ReelSubmissionRequest) -> ReelSubmissionResponse:
    return ReelSubmissionResponse(
        user_id=request.user_id,
        reel_url=request.reel_url,
    )