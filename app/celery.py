"""Celery configuration and task management.

This module sets up the Celery application for asynchronous task processing,
including RAG evaluation tasks.
"""

from celery import Celery  # type: ignore[import-untyped]

from app.config import settings

celery_app = Celery(
    "tasks", broker=str(settings.REDIS_URL), backend=str(settings.REDIS_URL), include=["app.tasks.evaluation"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
