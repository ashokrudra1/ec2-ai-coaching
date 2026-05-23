import logging
from sqlalchemy.orm import Session

from backend.models import CoachMemory

logger = logging.getLogger(__name__)


# =========================
# 💾 SAVE MESSAGE
# =========================
def save_message(db: Session, user_id: int, role: str, content: str):
    """
    Save conversation message to memory
    role: "user" | "assistant" | "system"
    """
    try:
        memory = CoachMemory(
            user_id=user_id,
            role=role,
            content=content
        )

        db.add(memory)
        db.commit()

    except Exception:
        db.rollback()
        logger.exception("❌ Failed to save message")


# =========================
# 📖 GET RECENT MEMORY
# =========================
def get_recent_memory(db: Session, user_id: int, limit: int = 6):
    """
    Fetch recent conversation history (latest first)
    """
    try:
        return (
            db.query(CoachMemory)
            .filter_by(user_id=user_id)
            .order_by(CoachMemory.created_at.desc())
            .limit(limit)
            .all()
        )

    except Exception:
        logger.exception("❌ Failed to fetch memory")
        return []


# =========================
# 🧹 CLEAR USER MEMORY (OPTIONAL)
# =========================
def clear_memory(db: Session, user_id: int):
    """
    Deletes all memory for a user
    Useful for reset/debug
    """
    try:
        db.query(CoachMemory).filter_by(user_id=user_id).delete()
        db.commit()

        logger.info(f"🧹 Memory cleared for user {user_id}")

    except Exception:
        db.rollback()
        logger.exception("❌ Failed to clear memory")
