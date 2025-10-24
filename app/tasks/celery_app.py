"""
Celery application configuration.
"""

import os
from celery import Celery
from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "planetal",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.payments"]  # Auto-discover tasks
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,
    result_expires=3600,  # Results expire after 1 hour
)

# Task routing (optional - for different queues)
celery_app.conf.task_routes = {
    "app.tasks.payments.*": {"queue": "payments"},
    "app.tasks.emails.*": {"queue": "emails"},
}

# Set default queue
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"
