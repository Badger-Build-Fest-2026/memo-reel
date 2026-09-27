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
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.knowledge import ReelKnowledge
from app.services.bundling.builder import build_content_bundle
from app.services.frame_extraction.extractor import extract_important_frames
from app.services.knowledge_extraction.gemini_client import extract_structured_knowledge
from app.services.transcription.transcriber import transcribe_video


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
    frames_dir = os.path.join(output_base_dir, reel_id, "frames")

    # Frame extraction and transcription don't depend on each other -
    # run them concurrently rather than sequentially.
    frame_task = asyncio.to_thread(
        extract_important_frames,
        video_path=video_path,
        output_dir=frames_dir,
        max_frames=max_frames,
    )
    transcript_task = asyncio.to_thread(
        transcribe_video,
        video_path,
        model_size=whisper_model,
    )

    frame_result, transcript_result = await asyncio.gather(frame_task, transcript_task)

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