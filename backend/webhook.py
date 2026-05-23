import logging

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


@router.post("/webhook/telegram")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def telegram_webhook(request: Request):
    """
    Secure Telegram webhook gateway.

    Flow:
    1. Validate Telegram secret token
    2. Accept payload
    3. Offload heavy work to Celery
    4. Immediately return 200 OK
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

        logger.warning("=== TELEGRAM WEBHOOK RECEIVED ===")

        if telegram_secret_header:
            logger.warning("Webhook secret header received")
        else:
            logger.warning("Webhook secret header missing")

        if telegram_secret_header != settings.TELEGRAM_SECRET_TOKEN:

            logger.warning({
                "event": "security_violation",
                "detail": "Unauthorized Telegram webhook token rejected"
            })

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # =========================
        # PARSE PAYLOAD
        # =========================

        body = await request.json()

        logger.info({
            "event": "telegram_update_received"
        })

        # =========================
        # ASYNC CELERY HANDOFF
        # =========================

        trigger_durable_webhook_handler.delay(body)

        logger.info({
            "event": "telegram_update_queued"
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
            f"FULL WEBHOOK FAILURE: {str(e)}"
        )

        logger.error(
            traceback.format_exc()
        )

        # Still ACK telegram
        return {
            "ok": True,
            "error": "Webhook processing failed internally"
        }
