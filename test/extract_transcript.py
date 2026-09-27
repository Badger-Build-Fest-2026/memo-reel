"""
CLI for testing audio transcription on a local video.

Usage:
    python extract_transcript.py input/reel.mp4
    python extract_transcript.py input/reel.mp4 --model small
"""

import argparse
import sys

from app.services.transcription.transcriber import transcribe_video


def main():
    parser = argparse.ArgumentParser(description="Transcribe a video's audio track.")
    parser.add_argument("video_path")
    parser.add_argument(
        "--model", default="base",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper model size. base = good speed/accuracy tradeoff for a hackathon.",
    )
    parser.add_argument("--output", default="output/transcript.json")
    args = parser.parse_args()

    print(f"Transcribing {args.video_path} (model={args.model}) ...")
    result = transcribe_video(args.video_path, model_size=args.model)

    print(f"✓ Language: {result.language}")
    print(f"✓ Duration: {result.duration_sec}s")
    print(f"✓ Segments: {len(result.segments)}")
    for seg in result.segments[:10]:
        print(f"    [{seg.start:>6.2f}s - {seg.end:>6.2f}s] {seg.text}")
    if len(result.segments) > 10:
        print(f"    ... and {len(result.segments) - 10} more")

    import os
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(result.model_dump_json(indent=2))
    print(f"✓ Transcript written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())