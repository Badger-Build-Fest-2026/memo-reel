"""
The Content Bundle is the payload that gets sent to the multimodal
AI step — not the raw video. It ties each selected frame to the
transcript text spoken around that moment, so the model gets
"what was on screen" + "what was said" already aligned in time,
instead of raw unaligned video.
"""

from pydantic import BaseModel


class ContentMoment(BaseModel):
    timestamp: float
    frame_path: str
    change_score: float
    spoken_text: str      # transcript text overlapping/near this frame's timestamp


class ContentBundle(BaseModel):
    video_path: str
    duration_sec: float
    language: str | None = None
    full_transcript: str
    moments: list[ContentMoment]

    # Instagram metadata — not derivable from the video itself, must
    # come from whatever captures the reel (Chrome extension / capture
    # layer). Optional here so this module stays testable standalone.
    reel_url: str | None = None
    caption: str | None = None
    timestamp: str | None = None   # ISO timestamp of when the user saved the reel