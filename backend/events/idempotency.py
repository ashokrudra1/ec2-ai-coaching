import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import ProcessedEvent
from backend.observability.metrics import record_counter

logger = logging.getLogger(__name__)


def claim_event(
    db: Session,
    *,
    event_id: str,
    source: str,
    user_id: Optional[int] = None,
    strict_mode: bool = False,
) -> bool:
    """
    Returns True if the event was claimed (not previously processed),
    False if it is a duplicate.
    """
    if not event_id:
        # No idempotency key available; proceed without dedupe.
        record_counter("idempotency.claim.missing_event_id", source=source)
        return True

    row = ProcessedEvent(event_id=event_id, source=source, user_id=user_id)
    try:
        db.add(row)
        db.commit()
        record_counter("idempotency.claim.accepted", source=source)
        return True
    except IntegrityError:
        db.rollback()
        record_counter("idempotency.claim.duplicate", source=source)
        return False
    except Exception:
        db.rollback()
        logger.exception("Failed to claim event for idempotency")
        record_counter("idempotency.claim.error", source=source)
        # In strict mode we fail closed for better safety under partial outage.
        return not strict_mode

