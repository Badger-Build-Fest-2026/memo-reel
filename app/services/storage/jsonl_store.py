"""
Appends each processed reel as one line to a per-user JSONL file.
Simple, append-only, no DB needed for the hackathon - and it's the
natural format to read line-by-line later for the RAG/query step.

    output/users/{user_id}.jsonl

(One file per user, not a per-user folder - keeps this flat.)
"""

import os

from app.schemas.knowledge import ReelKnowledge


def append_reel_jsonl(
    knowledge: ReelKnowledge,
    user_id: str,
    base_dir: str = "output/users",
) -> str:
    os.makedirs(base_dir, exist_ok=True)
    path = os.path.join(base_dir, f"{user_id}.jsonl")

    with open(path, "a") as f:
        f.write(knowledge.model_dump_json() + "\n")  # compact, one line per reel

    return path