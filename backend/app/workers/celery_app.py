# backend/app/workers/celery_app.py
from __future__ import annotations
import os
from celery import Celery

broker = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL", "redis://redis:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", broker)

celery = Celery("titan", broker=broker, backend=backend)
celery.conf.update(
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)
