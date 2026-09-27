"""
Usage:
    export GEMINI_API_KEY=your_key_here
    python extract_knowledge.py output/content_bundle.json
"""

import argparse
import json
import os
import sys

from app.schemas.bundle import ContentBundle
from app.services.knowledge_extraction.gemini_client import extract_structured_knowledge


def main():
    parser = argparse.ArgumentParser(description="Turn a Content Bundle into structured knowledge via Gemini.")
    parser.add_argument("bundle_json", help="path to content_bundle.json from build_bundle.py")
    parser.add_argument("--model", default="gemini-3.5-flash")
    parser.add_argument("--output", default="output/knowledge.json")
    args = parser.parse_args()

    with open(args.bundle_json) as f:
        bundle = ContentBundle(**json.load(f))

    print(f"Sending {len(bundle.moments)} frames + transcript to {args.model} ...")
    knowledge = extract_structured_knowledge(bundle, model_name=args.model)

    print(f"\n✓ Topic: {knowledge.topic}")
    print(f"✓ Concepts: {', '.join(knowledge.concepts)}")
    if knowledge.resources:
        print(f"✓ Resources: {', '.join(knowledge.resources)}")
    print(f"✓ Summary: {knowledge.summary}")
    print(f"✓ Evidence items: {len(knowledge.evidence)}")
    for e in knowledge.evidence:
        print(f"    [{e.timestamp:>6.2f}s] {e.claim}  ({e.frame_path})")

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(knowledge.model_dump_json(indent=2))
    print(f"\n✓ Structured knowledge written to {args.output}")


if __name__ == "__main__":
    sys.exit(main())