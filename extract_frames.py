"""
CLI for testing the frame extractor on a local video, no API needed.

Usage:
    python extract_frames.py input/reel.mp4
    python extract_frames.py input/reel.mp4 --max-frames 12 --min-gap 2.0
"""

import argparse
import json
import sys

from app.services.frame_extraction.extractor import (
    CHANGE_THRESHOLD,
    MIN_GAP_SEC,
    SAMPLE_INTERVAL_SEC,
    extract_important_frames,
)


def main():
    parser = argparse.ArgumentParser(description="Extract representative frames from a video.")
    parser.add_argument("video_path")
    parser.add_argument("--output-dir", default="output/frames")
    parser.add_argument("--max-frames", type=int, default=15)
    parser.add_argument("--sample-interval", type=float, default=SAMPLE_INTERVAL_SEC)
    parser.add_argument("--change-threshold", type=float, default=CHANGE_THRESHOLD)
    parser.add_argument("--min-gap", type=float, default=MIN_GAP_SEC)
    args = parser.parse_args()

    print(f"Loading {args.video_path} ...")
    result = extract_important_frames(
        video_path=args.video_path,
        output_dir=args.output_dir,
        max_frames=args.max_frames,
        sample_interval_sec=args.sample_interval,
        change_threshold=args.change_threshold,
        min_gap_sec=args.min_gap,
    )

    print(f"✓ Duration: {result.duration_sec}s")
    print(f"✓ FPS: {result.fps}")
    print(f"✓ Sampled: {result.sampled_frames} frames")
    print(f"✓ Candidates (above change threshold): {result.candidate_frames}")
    print(f"✓ Selected: {len(result.selected_frames)} representative frames")
    for f in result.selected_frames:
        print(f"    {f.timestamp:>6.2f}s  score={f.change_score:.3f}  {f.frame_path}")
    if result.contact_sheet_path:
        print(f"✓ Contact sheet: {result.contact_sheet_path}")

    results_json_path = f"{args.output_dir}/../results.json"
    with open(results_json_path, "w") as f:
        f.write(result.model_dump_json(indent=2))
    print(f"✓ Results written to {results_json_path}")


if __name__ == "__main__":
    sys.exit(main())