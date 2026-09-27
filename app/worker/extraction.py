import logging
import os
from typing import Any

from app.models.reel_submission import ReelSubmission

logger = logging.getLogger(__name__)


def _mock_knowledge_extraction(capture: ReelSubmission) -> dict[str, Any]:
    logger.info("Mock knowledge extraction received capture_id=%s", capture.capture_id)
    return {"mock": True, "capture_id": str(capture.capture_id)}


def run_knowledge_extraction(capture: ReelSubmission) -> dict[str, Any]:
    if os.getenv("WORKER_EXTRACTION_MODE", "live").lower() == "mock":
        return _mock_knowledge_extraction(capture)

    raise RuntimeError(
        "Reel content-bundle preparation is not connected to the API worker"
    )
