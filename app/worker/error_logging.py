import logging
import os
import re
from pathlib import Path
from threading import Lock

logger = logging.getLogger("app.worker.local_errors")
_write_lock = Lock()
_FILE_HANDLER_ATTRIBUTE = "_worker_error_log_handler"

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|"
        r"authorization|cookie|secret)\b\s*[:=]\s*[^\s,;]+"
    ),
    re.compile(r"(?i)(https?://[^\s?]+)\?[^\s]+"),
)


def _safe_error_summary(error: Exception) -> str:
    summaries = []
    current: BaseException | None = error
    while current is not None and len(summaries) < 4:
        summary = str(current).replace("\r", " ").replace("\n", " ").strip()
        for pattern in _SECRET_PATTERNS:
            summary = pattern.sub("[REDACTED]", summary)
        summaries.append(f"{type(current).__name__}: {summary[:4000]}")
        current = current.__cause__ or current.__context__
    return " <- ".join(summaries)[:6000] or "No exception message"


def _sanitize_log_message(message: str) -> str:
    message = message.replace("\r", " ").replace("\n", " ").strip()
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message[:2000]


class WorkerErrorFileHandler(logging.Handler):
    def __init__(self, log_path: Path):
        super().__init__(level=logging.ERROR)
        self.log_path = log_path

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = _sanitize_log_message(record.getMessage())
            if record.exc_info and record.exc_info[1]:
                exception = record.exc_info[1]
                message = (
                    f"{message} | exception="
                    f"{_safe_error_summary(exception)}"
                )
            with _write_lock:
                with self.log_path.open("a", encoding="utf-8") as error_log:
                    error_log.write(f"{message}\n")
        except Exception:
            self.handleError(record)


def configure_worker_error_logging() -> None:
    log_path = Path(os.getenv("WORKER_ERROR_LOG", "watchlogs/worker-errors.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    existing_handler = getattr(root_logger, _FILE_HANDLER_ATTRIBUTE, None)
    if existing_handler is not None:
        root_logger.removeHandler(existing_handler)
        existing_handler.close()

    handler = WorkerErrorFileHandler(log_path)
    root_logger.addHandler(handler)
    setattr(root_logger, _FILE_HANDLER_ATTRIBUTE, handler)


def log_worker_error(
    event: str,
    capture_id: str,
    error: Exception,
    *,
    stage: str | None = None,
) -> None:
    log_path = Path(os.getenv("WORKER_ERROR_LOG", "watchlogs/worker-errors.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    message = (
        f"event={event} capture_id={capture_id} stage={stage or 'unknown'} "
        f"error_type={type(error).__name__} error={_safe_error_summary(error)}"
    )
    try:
        with log_path.open("a", encoding="utf-8") as error_log:
            error_log.write(f"{message}\n")
    except OSError:
        logger.exception("Could not append worker error to %s", log_path)
        raise
