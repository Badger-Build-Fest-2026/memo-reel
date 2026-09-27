import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from app.models.reel_submission import ReelSubmission
from app.services.storage.persist import save_knowledge
from app.services.video_download import download_reel_video

logger = logging.getLogger(__name__)

DEFAULT_MEDIA_DIR = "media"


def _mock_knowledge_extraction(capture: ReelSubmission) -> dict[str, Any]:
    logger.info("Mock knowledge extraction received capture_id=%s", capture.capture_id)
    return {"mock": True, "capture_id": str(capture.capture_id)}


async def run_knowledge_extraction(capture: ReelSubmission) -> dict[str, Any]:
    if os.getenv("WORKER_EXTRACTION_MODE", "live").lower() == "mock":
        return _mock_knowledge_extraction(capture)

    media_dir = Path(os.getenv("PIPELINE_MEDIA_DIR", DEFAULT_MEDIA_DIR)).resolve()
    video_path = await asyncio.to_thread(
        download_reel_video,
        capture.source_url,
        capture.capture_id,
        str(media_dir / "videos"),
    )
    capture_output_dir = media_dir / "output" / str(capture.capture_id)
    knowledge = await run_pipeline(
        video_path=str(video_path),
        reel_url=capture.source_url,
        caption=capture.caption,
        saved_at=capture.requested_at.isoformat(),
        reel_id=str(capture.capture_id),
        output_base_dir=str(capture_output_dir / "pipeline"),
    )
    paths = save_knowledge(knowledge, output_dir=str(capture_output_dir))
    json_path = Path(paths["json_path"]).resolve()
    if json_path.parent != capture_output_dir.resolve():
        raise RuntimeError("Pipeline output path escaped its capture directory")
    logger.info(
        "Reel pipeline completed capture_id=%s json_path=%s",
        capture.capture_id,
        json_path,
    )
    return {"json_path": str(json_path)}


async def run_pipeline(**kwargs: Any) -> Any:
    from app.services.pipeline import process_reel

    return await process_reel(**kwargs)
