from celery import Celery

from app.config import settings

celery_app = Celery(
    "txn_pipeline",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)

# Ensure task module is imported so the worker registers it.
import app.worker.tasks  # noqa: E402,F401
