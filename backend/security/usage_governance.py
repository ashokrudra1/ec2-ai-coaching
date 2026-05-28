# backend/security/usage_governance.py
import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.models import User, AICostEvent

logger = logging.getLogger(__name__)

class UsageGovernor:
    @staticmethod
    def is_quota_exceeded(db: Session, user_id: int) -> bool:
        """Checks if the athlete has exceeded their monthly token allowance."""
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            return True
            
        # Protect against empty quotas
        quota = user.monthly_token_quota or 500000
        used = user.monthly_tokens_used or 0
        
        if used >= quota:
            logger.warning(f"🚨 [QUOTA EXCEEDED] User {user_id} blocked. Current usage: {used}/{quota} tokens.")
            return True
        return False

    @staticmethod
    def log_token_usage(db: Session, user_id: int, tokens_consumed: int):
        """Records token usage and persists the metrics to the database."""
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                user.monthly_tokens_used = (user.monthly_tokens_used or 0) + tokens_consumed
                db.commit()
                logger.info(f"📊 Tokens logged for User {user_id}: +{tokens_consumed} (Total: {user.monthly_tokens_used})")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to log token usage: {str(e)}")

    @staticmethod
    def log_cost_event(
        db: Session,
        *,
        user_id: Optional[int],
        org_id: Optional[str],
        feature: str,
        provider: Optional[str],
        model: Optional[str],
        tokens_estimated: Optional[int],
        cost_usd_estimated: Optional[float],
        correlation_id: Optional[str],
    ) -> None:
        try:
            row = AICostEvent(
                user_id=user_id,
                org_id=org_id,
                feature=feature,
                provider=provider,
                model=model,
                tokens_estimated=tokens_estimated,
                cost_usd_estimated=cost_usd_estimated,
                correlation_id=correlation_id,
            )
            db.add(row)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to write AICostEvent")
