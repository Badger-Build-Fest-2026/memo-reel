import asyncio
from pathlib import Path

from app.db.session import Base, get_engine
from app.models.capture_knowledge import CaptureKnowledge  # noqa: F401
from app.models.reel_submission import ReelSubmission  # noqa: F401

MIGRATION_PATHS = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "20260926_add_capture_job_state.sql",
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "20260927_add_capture_knowledge.sql",
)


async def migrate() -> None:
    engine = get_engine()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            for migration_path in MIGRATION_PATHS:
                statements = [
                    statement.strip()
                    for statement in migration_path.read_text().split(";")
                    if statement.strip()
                ]
                for statement in statements:
                    await connection.exec_driver_sql(statement)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
