# backend/daily_coach.py
import logging

from backend.database import SessionLocal
from backend.models import User
from backend.orchestration.coach_service import CoachService
from backend.notifications import send_telegram_message

logger = logging.getLogger(__name__)

def run_daily_coach():
    """
    Assembles a proactive morning training protocol 
    sent directly to athletes at 6:00 AM IST.
    """
    db = SessionLocal()

    try:
        users = db.query(User).all()
        if not users:
            logger.info("No active users registered for morning briefings.")
            return

        for user in users:
            try:
                if not user.telegram_chat_id:
                    continue

                # Trigger the multi-agent orchestration service with a directive prompt
                response = CoachService.generate(
                    db=db,
                    user_id=user.id,
                    user_input="Assess my readiness scores and detail today's precise running instruction."
                )

                # Broadcast directly to athlete's Telegram handle
                send_telegram_message(response, user.telegram_chat_id)
                logger.info(f"🌅 Morning briefing broadcast successfully to user {user.id}")

            except Exception:
                logger.exception(f"❌ Morning briefing failed for user {user.id}")

    except Exception:
        logger.exception("❌ Daily briefing pipeline failed.")

    finally:
        db.close()
