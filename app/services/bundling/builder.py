"""
Merges the frame extractor's output with the transcriber's output
into one Content Bundle, keyed by timestamp. This is the payload
the multimodal AI step consumes.

Matching strategy: for each selected frame, find transcript segments
that overlap its timestamp. If none overlap exactly (common — frames
are picked by visual change, not by speech boundaries), fall back to
the nearest segment within a small window, so the frame still gets
useful context instead of an empty string.
"""

from app.schemas.bundle import ContentBundle, ContentMoment
from app.schemas.frame import FrameExtractionResult
from app.schemas.transcript import TranscriptResult

NEAREST_WINDOW_SEC = 3.0  # how far to look for context if no segment directly overlaps


def _spoken_text_for_timestamp(ts: float, transcript: TranscriptResult) -> str:
    overlapping = [
        seg.text for seg in transcript.segments
        if seg.start <= ts <= seg.end
    ]
    if overlapping:
        return " ".join(overlapping)

    # No exact overlap - grab the closest segment within the window,
    # since frames don't line up perfectly with speech boundaries.
    nearby = [
        (min(abs(ts - seg.start), abs(ts - seg.end)), seg.text)
        for seg in transcript.segments
        if min(abs(ts - seg.start), abs(ts - seg.end)) <= NEAREST_WINDOW_SEC
    ]
    if not nearby:
        return ""
    nearby.sort(key=lambda x: x[0])
    return nearby[0][1]


def build_content_bundle(
    frame_result: FrameExtractionResult,
    transcript_result: TranscriptResult,
) -> ContentBundle:
    moments = [
        ContentMoment(
            timestamp=frame.timestamp,
            frame_path=frame.frame_path,
            change_score=frame.change_score,
            spoken_text=_spoken_text_for_timestamp(frame.timestamp, transcript_result),
        )
        for frame in frame_result.selected_frames
    ]

    return ContentBundle(
        video_path=frame_result.video_path,
        duration_sec=frame_result.duration_sec,
        language=transcript_result.language,
        full_transcript=transcript_result.full_text,
        moments=moments,
    )