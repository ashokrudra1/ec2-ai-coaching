import logging
from fastapi import APIRouter, Request, BackgroundTasks

from backend.strava_manager import strava_manager

router = APIRouter(prefix="/webhook", tags=["strava"])
logger = logging.getLogger(__name__)


# =========================
# ✅ STRAVA WEBHOOK VALIDATION
# =========================
@router.get("/strava")
async def strava_webhook_validation(request: Request):
    """
    Strava subscription verification endpoint
    """
    params = request.query_params
    hub_challenge = params.get("hub.challenge")

    return {"hub.challenge": hub_challenge}


# =========================
# 📡 STRAVA EVENT HANDLER
# =========================
@router.post("/strava")
async def strava_webhook_event(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handles Strava webhook events (activity create)
    """
    try:
        data = await request.json()

        logger.info(f"📡 Strava webhook received: {data}")

        # Only process new activities
        if data.get("aspect_type") == "create" and data.get("object_type") == "activity":
            athlete_id = data.get("owner_id")
            activity_id = data.get("object_id")

            if athlete_id and activity_id:
                # 🔥 Process in background (non-blocking)
                background_tasks.add_task(
                    strava_manager.handle_webhook,
                    athlete_id,
                    activity_id
                )
            else:
                logger.warning("⚠️ Missing athlete_id or activity_id")

        return {"status": "received"}

    except Exception:
        logger.exception("❌ Strava webhook processing failed")
        return {"status": "error"}
