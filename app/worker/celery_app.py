import os

from celery import Celery
from celery.signals import after_setup_logger, after_setup_task_logger
from dotenv import load_dotenv

from app.worker.error_logging import configure_worker_error_logging

load_dotenv()

celery_app = Celery(
    "recallgraph",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    imports=("app.worker.tasks", "app.worker.startup"),
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_ignore_result=True,
    task_store_errors_even_if_ignored=False,
    worker_concurrency=2,
    worker_pool="threads",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


def _configure_worker_error_log(**_kwargs) -> None:
    configure_worker_error_logging()


configure_worker_error_logging()
after_setup_logger.connect(_configure_worker_error_log, weak=False)
after_setup_task_logger.connect(_configure_worker_error_log, weak=False)
