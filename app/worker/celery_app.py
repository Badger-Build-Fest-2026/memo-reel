import os

from celery import Celery
from dotenv import load_dotenv

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
