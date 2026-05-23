# backend/celery_app.py
import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "veda_coach_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "backend.tasks.sync_tasks",
        "backend.tasks.coaching_tasks"
    ]
)

# Operational Configuration for High-Performance Async Operations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=False,
    worker_prefetch_multiplier=1,
    task_acks_late=True,

    # Dedicated Task Route Separators (Solves Queue Starvation)
    task_routes={
        "backend.tasks.coaching_tasks.generate_async_response": {"queue": "chat_critical"},
        "backend.tasks.sync_tasks.trigger_periodic_sync": {"queue": "data_sync"},
        "backend.tasks.sync_tasks.trigger_onboarding_backfill": {"queue": "onboarding_heavy"},
        "backend.tasks.coaching_tasks.trigger_daily_morning_briefing": {"queue": "scheduled_reports"},
        "backend.tasks.sync_tasks.trigger_snapshot_refresh": {"queue": "scheduled_reports"},
        "backend.tasks.coaching_tasks.trigger_weekly_compression": {"queue": "scheduled_reports"}, # Added routing for weekly compression
    }
)

celery_app.conf.beat_schedule = {
    "run-activity-sync-every-5-minutes": {
        "task": "backend.tasks.sync_tasks.trigger_periodic_sync",
        "schedule": 300.0,
    },
    "run-daily-morning-briefing-at-6am": {
        "task": "backend.tasks.coaching_tasks.trigger_daily_morning_briefing",
        "schedule": crontab(hour=6, minute=0),
    },
    "refresh-athlete-snapshots-every-30-minutes": {
        "task": "backend.tasks.sync_tasks.trigger_snapshot_refresh",
        "schedule": 1800.0, # Exactly 30 minutes
    },
    # 🧹 Added Memory Compression: Wakes up every Sunday at midnight
    "weekly-memory-compression": {
        "task": "backend.tasks.coaching_tasks.trigger_weekly_compression",
        "schedule": crontab(hour=0, minute=0, day_of_week=0),
    }
}
