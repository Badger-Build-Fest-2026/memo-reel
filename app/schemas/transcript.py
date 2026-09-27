"""
Schemas for the audio transcription output.

Segment-level timestamps are the whole point here — this is what
lets the Content Bundle step line up "what was said" with "what was
on screen" for a given moment in the reel.
"""

from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    start: float       # seconds
    end: float          # seconds
    text: str


class TranscriptResult(BaseModel):
    video_path: str
    language: str | None = None
    duration_sec: float | None = None
    full_text: str
    segments: list[TranscriptSegment]