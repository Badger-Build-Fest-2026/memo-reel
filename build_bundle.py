"""
Builds a Content Bundle from the JSON outputs you already have on
disk (no need to re-run extraction/transcription).

Usage:
    python build_bundle.py output/results.json output/transcript.json
"""

import argparse
import json
import os
import sys

from app.schemas.frame import FrameExtractionResult
from app.schemas.transcript import TranscriptResult
from app.services.bundling.builder import build_content_bundle


def main():
    parser = argparse.ArgumentParser(description="Merge frame + transcript JSON into a Content Bundle.")
    parser.add_argument("frames_json", help="path to results.json from extract_frames.py")
    parser.add_argument("transcript_json", help="path to transcript.json from extract_transcript.py")
    parser.add_argument("--output", default="output/content_bundle.json")
    args = parser.parse_args()

    with open(args.frames_json) as f:
        frame_result = FrameExtractionResult(**json.load(f))
    with open(args.transcript_json) as f:
        transcript_result = TranscriptResult(**json.load(f))

    bundle = build_content_bundle(frame_result, transcript_result)

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