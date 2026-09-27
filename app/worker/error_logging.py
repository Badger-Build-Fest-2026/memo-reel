import logging
import os
from pathlib import Path

logger = logging.getLogger("app.worker.local_errors")


def log_worker_error(event: str, capture_id: str, error: Exception) -> None:
    log_path = Path(os.getenv("WORKER_ERROR_LOG", "watchlogs/worker-errors.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(handler.baseFilename) == log_path.resolve()
        for handler in logger.handlers
    ):
        handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        logger.propagate = False

    logger.error(
        "event=%s capture_id=%s error_type=%s",
        event,
        capture_id,
        type(error).__name__,
    )
