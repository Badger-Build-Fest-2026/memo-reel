"""
Frame extraction pipeline (V1).

    Video
      -> sample every SAMPLE_INTERVAL_SEC
      -> compute visual-change score vs last SELECTED frame
      -> keep if score > threshold AND min time gap satisfied
      -> save frame + contact sheet

No OCR, no AI reranking yet. This module's only job is answering
"which frames are visually different enough to be worth keeping?" -
not "what do these frames mean?".
"""

import os

import cv2

from app.schemas.frame import FrameExtractionResult, FrameMetadata
from app.services.frame_extraction.contact_sheet import build_contact_sheet
from app.services.frame_extraction.scoring import (
    passes_min_gap,
    to_comparable,
    visual_change_score,
)

# Defaults - tune these against real test videos, don't assume they're right.
SAMPLE_INTERVAL_SEC = 0.5
CHANGE_THRESHOLD = 0.08     # mean normalized pixel diff needed to count as "changed"
MIN_GAP_SEC = 1.5
MAX_FRAMES = 15


def extract_important_frames(
    video_path: str,
    output_dir: str = "output/frames",
    max_frames: int = MAX_FRAMES,
    sample_interval_sec: float = SAMPLE_INTERVAL_SEC,
    change_threshold: float = CHANGE_THRESHOLD,
    min_gap_sec: float = MIN_GAP_SEC,
    build_sheet: bool = True,
) -> FrameExtractionResult:
    """
    NOTE on output_dir when processing many reels (e.g. from the async
    pipeline): pass a reel-scoped path such as f"output/{reel_id}/frames"
    so different reels' frames/contact sheets don't overwrite each other.
    See app/services/pipeline.py, which does this automatically.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / fps if fps else 0.0

    frame_step = max(1, round(fps * sample_interval_sec))

    os.makedirs(output_dir, exist_ok=True)

    selected: list[FrameMetadata] = []
    last_selected_gray = None
    last_selected_ts: float | None = None
    sampled_count = 0
    candidate_count = 0

    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_idx % frame_step != 0:
            frame_idx += 1
            continue

        sampled_count += 1
        timestamp = frame_idx / fps
        gray = to_comparable(frame)

        if last_selected_gray is None:
            score = 1.0  # always keep the first sampled frame
        else:
            score = visual_change_score(last_selected_gray, gray)

        is_candidate = score >= change_threshold
        if is_candidate:
            candidate_count += 1

        if is_candidate and passes_min_gap(timestamp, last_selected_ts, min_gap_sec):
            frame_filename = f"frame_{len(selected):03d}_{timestamp:.2f}s.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_path, frame)

            selected.append(
                FrameMetadata(
                    timestamp=round(timestamp, 2),
                    frame_path=frame_path,
                    frame_index=frame_idx,
                    change_score=round(score, 4),
                )
            )
            last_selected_gray = gray
            last_selected_ts = timestamp

            if len(selected) >= max_frames:
                break

        frame_idx += 1

    cap.release()

    contact_sheet_path = None
    if build_sheet and selected:
        contact_sheet_path = build_contact_sheet(
            frame_paths=[f.frame_path for f in selected],
            timestamps=[f.timestamp for f in selected],
            output_path=os.path.join(output_dir, "..", "contact_sheet.jpg"),
        )

    return FrameExtractionResult(
        video_path=video_path,
        duration_sec=round(duration_sec, 2),
        fps=round(fps, 2),
        total_frames=total_frames,
        sampled_frames=sampled_count,
        candidate_frames=candidate_count,
        selected_frames=selected,
        contact_sheet_path=contact_sheet_path,
    )