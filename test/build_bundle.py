"""
Builds a Content Bundle from the JSON outputs you already have on
disk (no need to re-run extraction/transcription).

Usage:
    python build_bundle.py output/results.json output/transcript.json
    python build_bundle.py output/results.json output/transcript.json \
        --reel-url "https://instagram.com/reel/xyz" \
        --caption "5 system design concepts every engineer should know"
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from app.schemas.frame import FrameExtractionResult
from app.schemas.transcript import TranscriptResult
from app.services.bundling.builder import build_content_bundle


def main():
    parser = argparse.ArgumentParser(description="Merge frame + transcript JSON into a Content Bundle.")
    parser.add_argument("frames_json", help="path to results.json from extract_frames.py")
    parser.add_argument("transcript_json", help="path to transcript.json from extract_transcript.py")
    parser.add_argument("--reel-url", default=None, help="Instagram reel URL, from the capture layer")
    parser.add_argument("--caption", default=None, help="Instagram caption text, from the capture layer")
    parser.add_argument("--saved-at", default=None, help="ISO timestamp; defaults to now")
    parser.add_argument("--output", default="output/content_bundle.json")
    args = parser.parse_args()

    with open(args.frames_json) as f:
        frame_result = FrameExtractionResult(**json.load(f))
    with open(args.transcript_json) as f:
        transcript_result = TranscriptResult(**json.load(f))

    bundle = build_content_bundle(frame_result, transcript_result)
    bundle.reel_url = args.reel_url
    bundle.caption = args.caption
    bundle.saved_at = args.saved_at or datetime.now(timezone.utc).isoformat()

    print(f"✓ {len(bundle.moments)} moments merged")
    for m in bundle.moments:
        preview = (m.spoken_text[:60] + "...") if len(m.spoken_text) > 60 else m.spoken_text
        print(f"    {m.timestamp:>6.2f}s  \"{preview}\"")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(bundle.model_dump_json(indent=2))
    print(f"✓ Content bundle written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())