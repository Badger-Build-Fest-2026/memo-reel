import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from app.models.reel_submission import ReelSubmission
from app.services.storage.persist import save_knowledge
from app.services.video_download import download_reel_video

logger = logging.getLogger(__name__)

DEFAULT_MEDIA_DIR = "media"


class ExtractionStageError(RuntimeError):
    def __init__(self, stage: str):
        super().__init__(f"Reel extraction failed during {stage}")
        self.stage = stage


def _find_cached_knowledge(output_dir: Path) -> Path | None:
    valid_results = []
    for candidate in output_dir.glob("*.json"):
        try:
            with candidate.open(encoding="utf-8") as result_file:
                result = json.load(result_file)
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(result, dict)
            and isinstance(result.get("category"), str)
            and result["category"]
            and isinstance(result.get("title"), str)
            and result["title"]
        ):
            valid_results.append(candidate)
    if not valid_results:
        return None
    return max(valid_results, key=lambda path: path.stat().st_mtime)


def _mock_knowledge_extraction(capture: ReelSubmission) -> dict[str, Any]:
    logger.info("Mock knowledge extraction received capture_id=%s", capture.capture_id)
    return {"mock": True, "capture_id": str(capture.capture_id)}


async def run_knowledge_extraction(capture: ReelSubmission) -> dict[str, Any]:
    if os.getenv("WORKER_EXTRACTION_MODE", "live").lower() == "mock":
        return _mock_knowledge_extraction(capture)

    media_dir = Path(os.getenv("PIPELINE_MEDIA_DIR", DEFAULT_MEDIA_DIR)).resolve()
    capture_output_dir = media_dir / "output" / str(capture.capture_id)
    cached_knowledge = _find_cached_knowledge(capture_output_dir)
    if cached_knowledge is not None:
        logger.info(
            "Reusing saved Reel knowledge capture_id=%s json_path=%s",
            capture.capture_id,
            cached_knowledge,
        )
        return {"json_path": str(cached_knowledge)}

    try:
        video_path = await asyncio.to_thread(
            download_reel_video,
            capture.source_url,
            capture.capture_id,
            str(media_dir / "videos"),
        )
    except Exception as error:
        raise ExtractionStageError("video_download") from error

    try:
        knowledge = await run_pipeline(
            video_path=str(video_path),
            reel_url=capture.source_url,
            caption=capture.caption,
            saved_at=capture.requested_at.isoformat(),
            reel_id=str(capture.capture_id),
            output_base_dir=str(capture_output_dir / "pipeline"),
        )
    except Exception as error:
        raise ExtractionStageError("knowledge_pipeline") from error

    try:
        paths = save_knowledge(knowledge, output_dir=str(capture_output_dir))
        json_path = Path(paths["json_path"]).resolve()
    except Exception as error:
        raise ExtractionStageError("local_json_save") from error
    if json_path.parent != capture_output_dir.resolve():
        raise ExtractionStageError("local_json_validation")
    logger.info(
        "Reel pipeline completed capture_id=%s json_path=%s",
        capture.capture_id,
        json_path,
    )
    return {"json_path": str(json_path)}


async def run_pipeline(**kwargs: Any) -> Any:
    from app.services.pipeline import process_reel

    return await process_reel(**kwargs)
