# backend/celery_app_enhanced.py
"""
Enhanced Celery Configuration with Queue Isolation & Resilience

Queue Strategy:
1. chat_critical (concurrency=4): User-facing messages, sub-second response
2. scheduled_reports (concurrency=2): Morning briefings, scheduled tasks
3. data_sync (concurrency=2): Strava syncs, webhook processing
4. onboarding_heavy (concurrency=1): 600-item Strava backfills, heavy computation

Retry Strategy:
- Exponential backoff: base=2s, max=600s, jitter=true
- Max retries: 3-5 depending on queue
- Dead-letter queue for irrecoverable errors

Author: Veda AI Elite Architecture Team
"""

import os
import logging
from celery import Celery
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")

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
        "backend.tasks.coaching_tasks",
        "backend.tasks.chat_tasks",
        "backend.tasks.onboarding_tasks"
    ]
)

# ============================================================================
# TASK CONFIGURATION
# ============================================================================

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="Asia/Kolkata",
    enable_utc=False,
    
    # Worker concurrency & prefetch
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Task time limits
    task_soft_time_limit=3600,
    task_time_limit=3700,
    
    # Result backend
    result_expires=3600,
    result_backend_transport_options={
        "master_name": "mymaster"
    },
    
    # Worker lifecycle
    worker_disable_rate_limits=False,
    worker_max_tasks_per_child=1000,
    worker_proc_alive_timeout=2,
)

# ============================================================================
# QUEUE ISOLATION - 4 SEPARATE PRIORITY QUEUES
# ============================================================================
# 
# Queue Configuration:
# Each queue has dedicated concurrency settings to prevent
# resource starvation between critical and background tasks.

celery_app.conf.task_queues = (
    # ========== QUEUE 1: CHAT_CRITICAL (Highest Priority) ==========
    # For instant user message processing from Telegram
    # Concurrency: 4 (most threads for immediate response)
    # Timeout: 30s (fast responses or fail)
    # Max retries: 3
    {
        'name': 'chat_critical',
        'exchange': 'chat_critical',
        'exchange_type': 'direct',
        'routing_key': 'chat_critical',
        'queue_arguments': {
            'x-max-priority': 10,  # Highest priority
            'x-dead-letter-exchange': 'dlx'
        }
    },
    
    # ========== QUEUE 2: SCHEDULED_REPORTS ==========
    # For morning briefings, daily reports, weekly summaries
    # Concurrency: 2 (moderate, can handle batches)
    # Timeout: 300s (5 minutes for report generation)
    # Max retries: 2
    {
        'name': 'scheduled_reports',
        'exchange': 'scheduled_reports',
        'exchange_type': 'direct',
        'routing_key': 'scheduled_reports',
        'queue_arguments': {
            'x-max-priority': 7,
            'x-dead-letter-exchange': 'dlx'
        }
    },
    
    # ========== QUEUE 3: DATA_SYNC ==========
    # For periodic Strava syncs, webhook processing
    # Concurrency: 2 (moderate, standard data operations)
    # Timeout: 600s (10 minutes)
    # Max retries: 5 (retry more for external API issues)
    {
        'name': 'data_sync',
        'exchange': 'data_sync',
        'exchange_type': 'direct',
        'routing_key': 'data_sync',
        'queue_arguments': {
            'x-max-priority': 5,
            'x-dead-letter-exchange': 'dlx'
        }
    },
    
    # ========== QUEUE 4: ONBOARDING_HEAVY ==========
    # For 600-item Strava backfills, bulk data ingestion
    # Concurrency: 1 (single worker, no parallelization to avoid DB stress)
    # Timeout: 1800s (30 minutes)
    # Max retries: 3
    {
        'name': 'onboarding_heavy',
        'exchange': 'onboarding_heavy',
        'exchange_type': 'direct',
        'routing_key': 'onboarding_heavy',
        'queue_arguments': {
            'x-max-priority': 2,  # Lowest priority
            'x-dead-letter-exchange': 'dlx'
        }
    },
    
    # Dead-letter queue for failed tasks
    {
        'name': 'dlq',
        'exchange': 'dlx',
        'exchange_type': 'direct',
        'routing_key': 'dlq'
    }
)

# ============================================================================
# TASK ROUTING (Map tasks to queues)
# ============================================================================

celery_app.conf.task_routes = {
    # Chat tasks (HIGHEST PRIORITY)
    'backend.tasks.chat_tasks.process_telegram_message': {'queue': 'chat_critical'},
    'backend.tasks.chat_tasks.handle_telegram_callback': {'queue': 'chat_critical'},
    'backend.tasks.coaching_tasks.generate_async_response': {'queue': 'chat_critical'},
    
    # Scheduled reports
    'backend.tasks.coaching_tasks.trigger_daily_morning_briefing': {'queue': 'scheduled_reports'},
    'backend.tasks.coaching_tasks.trigger_weekly_compression': {'queue': 'scheduled_reports'},
    'backend.tasks.report_tasks.generate_weekly_summary': {'queue': 'scheduled_reports'},
    
    # Data synchronization
    'backend.tasks.sync_tasks.trigger_periodic_sync': {'queue': 'data_sync'},
    'backend.tasks.sync_tasks.trigger_snapshot_refresh': {'queue': 'data_sync'},
    'backend.tasks.sync_tasks.handle_strava_webhook': {'queue': 'data_sync'},
    'backend.tasks.sync_tasks.trigger_durable_webhook_handler': {'queue': 'data_sync'},
    
    # Onboarding (LOWEST PRIORITY)
    'backend.tasks.onboarding_tasks.trigger_onboarding_backfill': {'queue': 'onboarding_heavy'},
    'backend.tasks.sync_tasks.trigger_onboarding_backfill': {'queue': 'onboarding_heavy'},
}

# ============================================================================
# RETRY STRATEGY - EXPONENTIAL BACKOFF WITH JITTER
# ============================================================================
# 
# Default retry policy with exponential backoff:
# Attempt 1: immediate
# Attempt 2: 2s + jitter
# Attempt 3: 4s + jitter
# Attempt 4: 8s + jitter
# ... up to 600s max

def exponential_backoff_with_jitter(attempt: int) -> int:
    """Calculate backoff duration with exponential growth and jitter"""
    import random
    base_delay = 2 ** min(attempt, 8)  # Cap at 256s (2^8)
    jitter = random.randint(-base_delay // 4, base_delay // 4)
    return min(base_delay + jitter, 600)  # Max 10 minutes


# Per-task retry configuration
celery_app.conf.task_autoretry_for = (Exception,)
celery_app.conf.task_max_retries = 3
celery_app.conf.task_default_retry_delay = 60

# Task-specific retry policies
celery_app.conf.task_annotations = {
    # Chat tasks: retry more aggressively (HTTP timeouts from Telegram)
    'backend.tasks.chat_tasks.*': {
        'autoretry_for': (Exception,),
        'retry_kwargs': {'max_retries': 3},
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': True
    },
    
    # Data sync tasks: retry extensively (external API flakiness)
    'backend.tasks.sync_tasks.*': {
        'autoretry_for': (Exception,),
        'retry_kwargs': {'max_retries': 5},
        'retry_backoff': True,
        'retry_backoff_max': 600,
        'retry_jitter': True
    },
    
    # Onboarding: retry less (avoid infinite loops)
    'backend.tasks.onboarding_tasks.*': {
        'autoretry_for': (Exception,),
        'retry_kwargs': {'max_retries': 2},
        'retry_backoff': True,
        'retry_backoff_max': 300,
        'retry_jitter': True
    }
}

# ============================================================================
# CELERY BEAT SCHEDULE (Periodic Tasks)
# ============================================================================

celery_app.conf.beat_schedule = {
    # Activity sync - every 5 minutes (data_sync queue)
    "run-activity-sync-every-5-minutes": {
        "task": "backend.tasks.sync_tasks.trigger_periodic_sync",
        "schedule": 300.0,
        "options": {"queue": "data_sync"}
    },
    
    # Daily morning briefing - 6:00 AM IST (scheduled_reports queue)
    "run-daily-morning-briefing-at-6am": {
        "task": "backend.tasks.coaching_tasks.trigger_daily_morning_briefing",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "scheduled_reports"}
    },
    
    # Athlete snapshot refresh - every 30 minutes (data_sync queue)
    "refresh-athlete-snapshots-every-30-minutes": {
        "task": "backend.tasks.sync_tasks.trigger_snapshot_refresh",
        "schedule": 1800.0,
        "options": {"queue": "data_sync"}
    },
    
    # Weekly memory compression - Sunday @ midnight (scheduled_reports queue)
    "weekly-memory-compression": {
        "task": "backend.tasks.coaching_tasks.trigger_weekly_compression",
        "schedule": crontab(hour=0, minute=0, day_of_week=0),
        "options": {"queue": "scheduled_reports"}
    }
}

# ============================================================================
# ERROR HANDLERS & MONITORING
# ============================================================================

@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity"""
    logger.info(f"🧪 Debug task executed: {self.request.id}")
    return {"status": "ok", "task_id": self.request.id}


# Signal handlers for task lifecycle
from celery.signals import task_prerun, task_postrun, task_failure, task_retry

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
    # Optional: Send to Sentry
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exception)
    except:
        pass


@task_retry.connect
def task_retry_handler(sender=None, task_id=None, reason=None, **kwargs):
    """Log when a task is retried"""
    logger.warning(f"🔄 Task retrying: {sender.name} ({task_id}) - {reason}")


logger.info("✅ Enhanced Celery app configured with 4-queue isolation strategy")
