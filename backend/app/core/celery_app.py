"""
Celery application configuration for async task processing.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "analisador_curriculos",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.document_tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    result_expires=3600,  # Results expire after 1 hour
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # Soft limit at 4 minutes
)

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.document_tasks.*": {"queue": "documents"},
    "app.tasks.search_tasks.*": {"queue": "search"},
}

# Result backend settings
celery_app.conf.result_backend_transport_options = {
    "master_name": "mymaster",
    "visibility_timeout": 3600,
}
