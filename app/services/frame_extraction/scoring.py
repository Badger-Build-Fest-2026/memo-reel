"""
Scoring logic for frame selection.

V1 signal set: visual change only (mean abs pixel diff on downscaled
grayscale). Text/info density signals get added in Phase 2.
"""

import cv2
import numpy as np


def to_comparable(frame: np.ndarray, size: tuple[int, int] = (160, 90)) -> np.ndarray:
    """
    Downscale + grayscale a frame so diffing is fast and robust to
    small compression/motion noise. 160x90 is plenty for detecting
    real scene/slide changes; we don't need full resolution to diff.
    """
    small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return gray


def visual_change_score(prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
    """
    Mean absolute pixel difference between two downscaled grayscale
    frames, normalized to 0-255 range -> roughly 0-1 after /255.
    Higher = more visual change.
    """
    diff = cv2.absdiff(prev_gray, curr_gray)
    return float(np.mean(diff)) / 255.0


def passes_min_gap(timestamp: float, last_selected_ts: float | None, min_gap_sec: float) -> bool:
    """
    Reject a candidate if it's too close in time to the last frame
    we already selected. Prevents bursts of near-duplicate frames
    around a single noisy transition.
    """
    if last_selected_ts is None:
        return True
    return (timestamp - last_selected_ts) >= min_gap_sec