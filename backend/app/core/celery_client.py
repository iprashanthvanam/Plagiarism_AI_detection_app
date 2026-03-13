"""
Celery app instance — initialized once, used globally.
"""

import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize Celery app
celery_app = Celery(
    "plagiarism_analysis",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=120 * 60,  # Hard limit: 2 hours
    task_soft_time_limit=90 * 60,  # Soft limit: 90 minutes (allows graceful cleanup)
    result_expires=3600,  # Results expire after 1 hour
    broker_connection_retry_on_startup=True,
)

# ✅ AUTO-DISCOVER TASKS — must happen after celery_app is created
# This imports all task modules so Celery knows about them
celery_app.autodiscover_tasks(['app.tasks'])