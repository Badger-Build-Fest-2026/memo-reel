"""
Single backend entrypoint for the whole reel-processing pipeline:

    video.mp4
      -> frame extraction (OpenCV) \\
                                     >-- run concurrently
      -> transcription (Whisper)   /
      -> merge into Content Bundle
      -> Gemini call
      -> ReelKnowledge

Frame extraction and transcription are both blocking, synchronous
calls under the hood (OpenCV, ffmpeg subprocess, faster-whisper) -
neither has native asyncio support. asyncio.to_thread() runs each
in a thread pool so they execute concurrently instead of one after
the other, without needing to rewrite either module internally.

Each call is scoped to a reel_id so processing many reels doesn't
have them overwrite each other's frames/contact sheets - this is
the thing to use once you're calling this from an endpoint that
handles more than one reel.
"""

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.frame import FrameExtractionResult
from app.schemas.knowledge import ReelKnowledge
from app.schemas.transcript import TranscriptResult
from app.services.bundling.builder import build_content_bundle
from app.services.frame_extraction.extractor import extract_important_frames
from app.services.knowledge_extraction.gemini_client import extract_structured_knowledge
from app.services.transcription.transcriber import transcribe_video


_CACHE_VERSION = 1


def _video_signature(video_path: str) -> dict[str, str | int]:
    path = Path(video_path).resolve()
    stat = path.stat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "modified_ns": stat.st_mtime_ns,
    }


def _read_stage_cache(cache_path: Path, result_type, signature):
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if (
            cached.get("version") != _CACHE_VERSION
            or cached.get("video") != signature
        ):
            return None
        result = result_type.model_validate(cached["result"])
        if hasattr(result, "selected_frames") and any(
            not Path(frame.frame_path).is_file()
            for frame in result.selected_frames
        ):
            return None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _write_stage_cache(cache_path: Path, result) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_path.parent,
            prefix=f".{cache_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(
                {
                    "version": _CACHE_VERSION,
                    "video": _video_signature(result.video_path),
                    "result": result.model_dump(mode="json"),
                },
                temporary_file,
            )
        if temporary_path is None:
            raise RuntimeError("Temporary pipeline cache file was not created")
        os.replace(temporary_path, cache_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _default_reel_id(video_path: str) -> str:
    stem = Path(video_path).stem
    return f"{stem}_{uuid.uuid4().hex[:8]}"


async def process_reel(
    video_path: str,
    reel_url: str | None = None,
    caption: str | None = None,
    saved_at: str | None = None,
    reel_id: str | None = None,
    output_base_dir: str = "output",
    max_frames: int = 15,
    whisper_model: str = "base",
    gemini_model: str = "gemini-3.5-flash",
) -> ReelKnowledge:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    reel_id = reel_id or _default_reel_id(video_path)
    reel_output_dir = Path(output_base_dir) / reel_id
    frames_dir = str(reel_output_dir / "frames")
    cache_dir = reel_output_dir / "cache"
    signature = _video_signature(video_path)
    frame_cache = cache_dir / f"frames-{max_frames}.json"
    transcript_cache = cache_dir / f"transcript-{whisper_model}.json"

    async def get_frames():
        cached = _read_stage_cache(frame_cache, FrameExtractionResult, signature)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(
            extract_important_frames,
            video_path=video_path,
            output_dir=frames_dir,
            max_frames=max_frames,
        )
        _write_stage_cache(frame_cache, result)
        return result

    async def get_transcript():
        cached = _read_stage_cache(transcript_cache, TranscriptResult, signature)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(
            transcribe_video,
            video_path,
            model_size=whisper_model,
        )
        _write_stage_cache(transcript_cache, result)
        return result

    frame_result, transcript_result = await asyncio.gather(
        get_frames(),
        get_transcript(),
    )

    bundle = build_content_bundle(frame_result, transcript_result)
    bundle.reel_url = reel_url
    bundle.caption = caption
    bundle.saved_at = saved_at or datetime.now(timezone.utc).isoformat()

    # The Gemini SDK call is also a blocking network call - offload it
    # too so it doesn't block the event loop while waiting on the API.
    knowledge = await asyncio.to_thread(
        extract_structured_knowledge,
        bundle,
        model_name=gemini_model,
    )

    return knowledge