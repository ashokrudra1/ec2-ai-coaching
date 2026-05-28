# backend/celery_app.py
"""
Celery application configuration for Veda AI Coaching.
Handles distributed task queue, async operations, and scheduled jobs.
"""
import os
import logging
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
STRAVA_BACKFILL_RATE_LIMIT = os.getenv("STRAVA_BACKFILL_RATE_LIMIT", "95/m")

logger.info(f"🔧 Initializing Celery with broker: {REDIS_URL.split('@')[1] if '@' in REDIS_URL else REDIS_URL}")
logger.info(f"📍 Environment: {ENVIRONMENT}")

# ============================================================================
# CELERY APP INITIALIZATION
# ============================================================================
celery_app = Celery(
    "veda_coach_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "backend.tasks.sync_tasks",
        "backend.tasks.coaching_tasks"
    ]
)

# ============================================================================
# TASK CONFIGURATION (High-Performance Async Operations)
# ============================================================================
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=False,
    
    # Worker concurrency settings
    worker_prefetch_multiplier=1,          # Process one task at a time
    task_acks_late=True,                   # Acknowledge after task completes
    task_reject_on_worker_lost=True,       # Reject tasks if worker dies
    
    # Task time limits
    task_soft_time_limit=3600,             # 1 hour soft limit
    task_time_limit=3700,                  # 1 hour 10 min hard limit
    
    # Result backend configuration
    result_expires=3600,                   # Forget results after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "connection_class": "rediscluster.StrictRedisCluster"
    },
    
    # Worker configuration
    worker_disable_rate_limits=False,
    worker_max_tasks_per_child=1000,       # Restart worker after 1000 tasks
    worker_proc_alive_timeout=2,           # Worker process timeout
    
    # Retry configuration
    task_autoretry_for=(Exception,),
    task_max_retries=3,
    task_default_retry_delay=60,           # Retry after 60 seconds
    task_annotations={
        "backend.tasks.sync_tasks.trigger_onboarding_backfill": {
            "rate_limit": STRAVA_BACKFILL_RATE_LIMIT
        },
        "backend.tasks.sync_tasks.process_strava_webhook_event": {
            "rate_limit": "95/m"
        }
    },
)

# ============================================================================
# TASK ROUTING (Queue Separation to Prevent Starvation)
# ============================================================================
# Different task types go to different queues to ensure critical tasks
# (like user interactions) aren't blocked by heavy sync operations.
celery_app.conf.task_routes = {
    # Critical user-facing tasks (highest priority)
    "backend.tasks.coaching_tasks.generate_async_response": {"queue": "chat_critical"},
    
    # Data synchronization tasks
    "backend.tasks.sync_tasks.trigger_periodic_sync": {"queue": "data_sync"},
    "backend.tasks.sync_tasks.trigger_onboarding_backfill": {"queue": "onboarding_heavy"},
    "backend.tasks.sync_tasks.trigger_durable_webhook_handler": {"queue": "data_sync"},
    "backend.tasks.sync_tasks.process_strava_webhook_event": {"queue": "data_sync"},
    "backend.tasks.sync_tasks.trigger_rate_limited_backfill_page": {"queue": "onboarding_heavy"},
    
    # Scheduled/batch operations
    "backend.tasks.coaching_tasks.trigger_daily_morning_briefing": {"queue": "scheduled_reports"},
    "backend.tasks.coaching_tasks.trigger_weekly_compression": {"queue": "scheduled_reports"},
    "backend.tasks.coaching_tasks.trigger_proactive_engagement": {"queue": "scheduled_reports"},
}

# ============================================================================
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ============================================================================
celery_app.conf.beat_schedule = {
    # Activity sync - runs every 5 minutes to fetch recent Strava activities
    "run-activity-sync-every-5-minutes": {
        "task": "backend.tasks.sync_tasks.trigger_periodic_sync",
        "schedule": 300.0,  # 5 minutes
        "options": {"queue": "data_sync"}
    },
    
    # Daily morning briefing - 6:00 AM IST
    "run-daily-morning-briefing-at-6am": {
        "task": "backend.tasks.coaching_tasks.trigger_daily_morning_briefing",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "scheduled_reports"}
    },
    
    # Athlete snapshot refresh - every 30 minutes
    "refresh-athlete-snapshots-every-30-minutes": {
        "task": "backend.tasks.sync_tasks.trigger_snapshot_refresh",
        "schedule": 1800.0,  # 30 minutes
        "options": {"queue": "data_sync"}
    },
    
    # Weekly memory compression - Every Sunday at midnight
    "weekly-memory-compression": {
        "task": "backend.tasks.coaching_tasks.trigger_weekly_compression",
        "schedule": crontab(hour=0, minute=0, day_of_week=0),
        "options": {"queue": "scheduled_reports"}
    },

    # Proactive engagement check-in - every 4 hours
    "proactive-engagement-every-4-hours": {
        "task": "backend.tasks.coaching_tasks.trigger_proactive_engagement",
        "schedule": 14400.0,
        "options": {"queue": "scheduled_reports"}
    }
}

# ============================================================================
# ERROR HANDLERS
# ============================================================================
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity"""
    logger.info(f"🧪 Debug task executed: {self.request.id}")
    return {"status": "ok", "task_id": self.request.id}


# ============================================================================
# SIGNAL HANDLERS
# ============================================================================
from celery.signals import task_prerun, task_postrun, task_failure

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Log when a task starts"""
    logger.debug(f"🚀 Task starting: {task.name} ({task_id})")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Log when a task completes"""
    logger.debug(f"✅ Task completed: {task.name} ({task_id})")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """Log when a task fails"""
    logger.error(f"❌ Task failed: {sender.name} ({task_id}) - {str(exception)}")


logger.info("✅ Celery app configured successfully")
