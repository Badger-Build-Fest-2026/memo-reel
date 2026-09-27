"""
Persistence for a finished ReelKnowledge result: writes the
individual JSON file (nicely named), and optionally appends it to
the user's JSONL log. Kept separate from app/services/pipeline.py
so extraction and persistence stay decoupled - process_reel() just
returns a ReelKnowledge, this decides where it lands on disk.
"""

import os

from app.schemas.knowledge import ReelKnowledge
from app.services.storage.jsonl_store import append_reel_jsonl
from app.services.storage.naming import make_filename


def save_knowledge(
    knowledge: ReelKnowledge,
    output_dir: str = "media/output",
    user_id: str | None = None,
) -> dict:
    """
    Returns {"json_path": ..., "jsonl_path": ... or None}
    """
    filename = make_filename(knowledge.category, knowledge.subcategory, knowledge.title)
    json_path = os.path.join(output_dir, filename)
    os.makedirs(output_dir, exist_ok=True)
    with open(json_path, "w") as f:
        f.write(knowledge.model_dump_json(indent=2))

    jsonl_path = None
    if user_id:
        jsonl_path = append_reel_jsonl(knowledge, user_id=user_id, base_dir=os.path.join(output_dir, "users"))

    return {"json_path": json_path, "jsonl_path": jsonl_path}