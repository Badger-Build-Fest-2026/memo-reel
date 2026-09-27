import argparse
import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select

from app.db.session import get_engine, get_sessionmaker
from app.models.reel_submission import ReelSubmission
from app.worker.tasks import process_capture_task


async def enqueue_recoverable_captures(limit: int = 100) -> int:
    now = datetime.now(timezone.utc)
    async with get_sessionmaker()() as session:
        capture_ids = (
            await session.scalars(
                select(ReelSubmission.capture_id)
                .where(
                    or_(
                        ReelSubmission.status == "queued",
                        (
                            (ReelSubmission.status == "processing")
                            & (ReelSubmission.lease_expires_at < now)
                        ),
                    )
                )
                .order_by(ReelSubmission.requested_at)
                .limit(limit)
            )
        ).all()

    for capture_id in capture_ids:
        process_capture_task.delay(str(UUID(capture_id)))
    return len(capture_ids)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Re-enqueue queued captures and expired processing leases."
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")

    engine = get_engine()
    try:
        count = asyncio.run(enqueue_recoverable_captures(args.limit))
        print(f"Re-enqueued {count} recoverable capture(s).")
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    main()
