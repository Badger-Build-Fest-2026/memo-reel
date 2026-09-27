import json
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.capture_knowledge import CaptureKnowledge
from app.models.reel_submission import ReelSubmission


async def save_knowledge_to_database(
    capture: ReelSubmission,
    json_path: str | Path,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with Path(json_path).open(encoding="utf-8") as knowledge_file:
        knowledge: Any = json.load(knowledge_file)

    if not isinstance(knowledge, dict):
        raise ValueError("Knowledge JSON must contain a JSON object")

    category = knowledge.get("category")
    obsidian_url = knowledge.get("obsidian_url")
    if not isinstance(category, str) or not category:
        raise ValueError("Knowledge JSON must contain a non-empty category")
    if obsidian_url is not None and not isinstance(obsidian_url, str):
        raise ValueError("Knowledge JSON obsidian_url must be a string or null")

    statement = insert(CaptureKnowledge).values(
        capture_id=capture.capture_id,
        user_id=capture.user_id,
        requested_at=capture.requested_at,
        obsidian_url=obsidian_url,
        category=category,
        knowledge_json=knowledge,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[CaptureKnowledge.capture_id],
        set_={
            "user_id": statement.excluded.user_id,
            "requested_at": statement.excluded.requested_at,
            "delivered_at": statement.excluded.delivered_at,
            "obsidian_url": statement.excluded.obsidian_url,
            "category": statement.excluded.category,
            "knowledge_json": statement.excluded.knowledge_json,
        },
    )

    async with session_factory() as session:
        await session.execute(statement)
        await session.commit()
