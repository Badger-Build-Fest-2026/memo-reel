"""
Runs the full pipeline exactly the way a backend endpoint would call
it - single async entrypoint, frames + transcript run concurrently.

Usage:
    export GEMINI_API_KEY=your_key_here
    python run_pipeline.py input/video.mp4
    python run_pipeline.py input/video.mp4 --reel-url "https://instagram.com/reel/xyz" \
        --caption "..." --user-id jay
"""

import argparse
import asyncio
import sys
import time

from app.services.pipeline import process_reel
from app.services.storage.persist import save_knowledge


async def main_async(args):
    start = time.time()
    knowledge = await process_reel(
        video_path=args.video_path,
        reel_url=args.reel_url,
        caption=args.caption,
        max_frames=args.max_frames,
        whisper_model=args.whisper_model,
        gemini_model=args.gemini_model,
    )
    elapsed = time.time() - start

    paths = save_knowledge(knowledge, output_dir=args.output_dir, user_id=args.user_id)

    print(f"\n✓ Done in {elapsed:.1f}s")
    print(f"✓ Title: {knowledge.title}")
    print(f"✓ Category: {knowledge.category} / {knowledge.subcategory}")
    print(f"✓ Summary: {knowledge.summary}")
    print(f"✓ Evidence items: {len(knowledge.evidence)}")
    print(f"✓ Written to {paths['json_path']}")
    if paths["jsonl_path"]:
        print(f"✓ Appended to {paths['jsonl_path']}")


def main():
    parser = argparse.ArgumentParser(description="Run the full reel-processing pipeline.")
    parser.add_argument("video_path")
    parser.add_argument("--reel-url", default=None)
    parser.add_argument("--caption", default=None)
    parser.add_argument("--user-id", default=None, help="if given, also appends to output/users/{user_id}/reels.jsonl")
    parser.add_argument("--max-frames", type=int, default=15)
    parser.add_argument("--whisper-model", default="base")
    parser.add_argument("--gemini-model", default="gemini-3.5-flash")
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())