# backend/tasks/coaching_tasks.py
import logging
from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.daily_coach import run_daily_coach
from backend.orchestration.coach_service import CoachService
from backend.notifications import send_telegram_message

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.tasks.coaching_tasks.trigger_daily_morning_briefing")
def trigger_daily_morning_briefing():
    logger.info("🌅 Celery Worker: Starting daily coaching morning briefings...")
    try:
        run_daily_coach()
        logger.info("✅ Celery Worker: Morning briefing tasks processed successfully.")
    except Exception as e:
        logger.error(f"❌ Celery Worker: Morning briefing task failed: {str(e)}", exc_info=True)


@celery_app.task(name="backend.tasks.coaching_tasks.generate_async_response")
def generate_async_response(user_id: int, chat_id: str, user_input: str):
    """
    Asynchronously processes the user message through the Multi-Agent council
    without blocking the FastAPI HTTP connection.
    """
    logger.info(f"🧠 Celery Worker: Processing multi-agent synthesis for User ID {user_id}...")
    db = SessionLocal()
    try:
        # 1. Generate the elite response
        response = CoachService.generate(db, user_id, user_input=user_input)

        # 2. Dispatch message directly to Telegram
        send_telegram_message(response, chat_id)
        logger.info(f"✅ Celery Worker: Response dispatched successfully to Chat ID {chat_id}")
    except Exception as e:
        logger.error(f"❌ Celery Worker: Async coaching generation failed: {str(e)}", exc_info=True)
    finally:
        db.close()


# 🧹 Added Task: Weekly Episodic Memory Compression
@celery_app.task(name="backend.tasks.coaching_tasks.trigger_weekly_compression")
def trigger_weekly_compression():
    """
    Enqueued by Celery Beat every Sunday at midnight.
    Loops through all registered users and compresses their historical chat vector table.
    """
    logger.info("🧹 Celery Worker: Initializing weekly episodic memory compression...")
    db = SessionLocal()
    try:
        from backend.models import User
        from backend.memory.memory_archiver import MemoryArchivalEngine
        
        users = db.query(User).all()
        for u in users:
            try:
                MemoryArchivalEngine.compress_old_memories(db, u.id)
            except Exception as user_err:
                logger.error(f"❌ Compression failed for User {u.id}: {str(user_err)}")
                continue
        logger.info("✅ Celery Worker: Weekly memory compression completed successfully.")
    except Exception as e:
        logger.error(f"❌ Celery Worker: Memory compression task failed: {str(e)}", exc_info=True)
    finally:
        db.close()
