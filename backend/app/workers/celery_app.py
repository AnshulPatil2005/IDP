# backend/app/workers/celery_app.py
"""
Celery application configuration module.
This module initializes a Celery app instance for the 'titan' project,
using broker and backend URLs from environment variables. It sets
various configuration options for reliable task processing, including:
- broker_connection_retry_on_startup: Enables broker connection retries on startup.
- task_acks_late: Ensures tasks are acknowledged only after completion.
- worker_prefetch_multiplier: Controls the number of tasks a worker prefetches.
- result_expires: Sets the expiration time for task results (in seconds).
Environment Variables:
- CELERY_BROKER_URL: URL for the Celery broker (e.g., Redis).
- REDIS_URL: Fallback URL for the broker if CELERY_BROKER_URL is not set.
- CELERY_RESULT_BACKEND: URL for storing task results (defaults to broker URL).
"""
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
