import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import ProcessedEvent

logger = logging.getLogger(__name__)


def claim_event(db: Session, *, event_id: str, source: str, user_id: Optional[int] = None) -> bool:
    """
    Returns True if the event was claimed (not previously processed),
    False if it is a duplicate.
    """
    if not event_id:
        # No idempotency key available; proceed without dedupe.
        return True

    row = ProcessedEvent(event_id=event_id, source=source, user_id=user_id)
    try:
        db.add(row)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    except Exception:
        db.rollback()
        logger.exception("Failed to claim event for idempotency")
        return True

