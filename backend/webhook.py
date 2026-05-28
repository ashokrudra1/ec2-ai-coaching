import logging
import hmac
import hashlib
import json
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config.settings import settings
from backend.tasks.sync_tasks import trigger_durable_webhook_handler

router = APIRouter()

logger = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address
)


class TelegramWebhookHandler:
    """Handler for Telegram webhook events with non-blocking processing."""
    
    @staticmethod
    def validate_secret(token: Optional[str]) -> bool:
        """Validate Telegram webhook secret token."""
        if not token:
            logger.warning("Missing Telegram webhook secret header")
            return False
        
        if token != settings.TELEGRAM_SECRET_TOKEN:
            logger.warning(f"Invalid Telegram webhook token: {token[:10]}...")
            return False
        
        return True
    
    @staticmethod
    def parse_message(body: Dict[str, Any]) -> tuple[bool, str]:
        """
        Parse Telegram message and classify type.
        Returns: (is_valid, message_type) where message_type is:
        - 'text': Regular text message
        - 'callback': Button click callback
        - 'document': PDF/file upload
        - 'unknown': Unrecognized message
        """
        if "callback_query" in body:
            return True, "callback"
        elif "message" in body:
            message = body["message"]
            if "document" in message:
                return True, "document"
            elif "text" in message:
                return True, "text"
        
        return False, "unknown"


class StravaWebhookHandler:
    """Handler for Strava webhook events with signature validation."""
    
    @staticmethod
    def validate_signature(body: bytes, signature: str) -> bool:
        """
        Validate Strava webhook signature using HMAC-SHA256.
        
        Strava sends the signature as X-Strava-Hook-Id header.
        We verify using the STRAVA_SIGNING_SECRET.
        """
        try:
            expected_signature = hmac.new(
                settings.STRAVA_SIGNING_SECRET.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature validation error: {e}")
            return False
    
    @staticmethod
    def check_duplicate_activity(db_session, user_id: int, strava_id: int) -> bool:
        """
        Check if activity already exists in database.
        Returns True if duplicate (skip), False if new (process).
        """
        try:
            from backend.models import Activity
            
            existing = db_session.query(Activity).filter_by(
                user_id=user_id,
                strava_id=strava_id
            ).first()
            
            return existing is not None
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return False


@router.post("/webhook/telegram")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def telegram_webhook(request: Request):
    """
    Secure Telegram webhook gateway.

    Flow:
    1. Validate Telegram secret token
    2. Parse payload and classify message type
    3. Validate message structure
    4. Offload heavy work to Celery (non-blocking)
    5. Immediately return 200 OK
    
    Supported messages:
    - Text messages: Enqueued to chat_critical queue
    - Callback queries: Button clicks handled in sync_tasks
    - Documents (PDF): Downloaded, text extracted, sent to medical insights
    """

    try:
        # =========================
        # TELEGRAM SECRET VALIDATION
        # =========================

        telegram_secret_header = (
            request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            or request.headers.get("x-telegram-bot-api-secret-token")
            or request.headers.get("X_Telegram_Bot_Api_Secret_Token")
        )

        if not TelegramWebhookHandler.validate_secret(telegram_secret_header):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # =========================
        # PARSE PAYLOAD
        # =========================

        body = await request.json()
        
        is_valid, msg_type = TelegramWebhookHandler.parse_message(body)
        
        if not is_valid:
            logger.debug("Received non-text/callback/document Telegram update, ignoring")
            return {"ok": True}

        logger.info({
            "event": "telegram_update_received",
            "message_type": msg_type,
            "update_id": body.get("update_id")
        })

        # =========================
        # MESSAGE ROUTING
        # =========================
        
        # All message types go through the same durable handler
        # The handler differentiates based on content (text vs callback vs document)
        trigger_durable_webhook_handler.delay(body)

        logger.info({
            "event": "telegram_update_queued",
            "message_type": msg_type
        })

        # =========================
        # INSTANT TELEGRAM ACK
        # =========================

        return {"ok": True}

    except HTTPException:
        raise

    except Exception as e:
        import traceback

        logger.error(
            f"TELEGRAM WEBHOOK FAILURE: {str(e)}"
        )

        logger.error(
            traceback.format_exc()
        )

        # Still ACK telegram (required by Telegram API)
        return {
            "ok": True,
            "error": "Webhook processing failed internally"
        }
