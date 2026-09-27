"""
Schemas for frame extraction output.

Kept deliberately minimal for V1 — no scoring breakdown yet
(that comes in Phase 2 with OCR/info-density signals).
"""

from pydantic import BaseModel


class FrameMetadata(BaseModel):
    timestamp: float          # seconds into the video
    frame_path: str           # path to saved jpg
    frame_index: int          # index in the sampled sequence (for debugging)
    change_score: float       # raw visual-change score vs previous kept frame


class FrameExtractionResult(BaseModel):
    video_path: str
    duration_sec: float
    fps: float
    total_frames: int
    sampled_frames: int
    candidate_frames: int
    selected_frames: list[FrameMetadata]
    contact_sheet_path: str | None = None