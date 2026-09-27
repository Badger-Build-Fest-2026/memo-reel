"""
Persistence for a finished ReelKnowledge result: writes the
individual JSON file (nicely named), and optionally appends it to
the user's JSONL log. Kept separate from app/services/pipeline.py
so extraction and persistence stay decoupled - process_reel() just
returns a ReelKnowledge, this decides where it lands on disk.
"""

import os
import tempfile
from pathlib import Path

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
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / filename
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path,
            prefix=f".{filename}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(knowledge.model_dump_json(indent=2))
        if temp_path is None:
            raise RuntimeError("Temporary knowledge JSON file was not created")
        os.replace(temp_path, json_path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    jsonl_path = None
    if user_id:
        jsonl_path = append_reel_jsonl(
            knowledge,
            user_id=user_id,
            base_dir=str(output_path / "users"),
        )

    return {"json_path": str(json_path), "jsonl_path": jsonl_path}