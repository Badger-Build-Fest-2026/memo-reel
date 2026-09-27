import asyncio
from pathlib import Path

from app.db.session import Base, get_engine
from app.models.reel_submission import ReelSubmission  # noqa: F401

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "migrations"
    / "20260926_add_capture_job_state.sql"
)


async def migrate() -> None:
    engine = get_engine()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            statements = [
                statement.strip()
                for statement in MIGRATION_PATH.read_text().split(";")
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
