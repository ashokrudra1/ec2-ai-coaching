import logging
import hmac
import hashlib
from fastapi import APIRouter, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.tasks.sync_tasks import process_strava_webhook_event
from backend.config.settings import settings

router = APIRouter(prefix="/webhook", tags=["strava"])
logger = logging.getLogger(__name__)

limiter = Limiter(
    key_func=get_remote_address
)


def validate_strava_signature(body: bytes, signature: str) -> bool:
    """
    Validate Strava webhook signature using HMAC-SHA256.
    
    Strava sends: X-Strava-Hook-Signature header
    We verify using: STRAVA_SIGNING_SECRET
    """
    try:
        expected_signature = hmac.new(
            settings.STRAVA_SIGNING_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(signature, expected_signature)
        if not is_valid:
            logger.warning(f"Invalid Strava signature. Expected: {expected_signature[:10]}..., Got: {signature[:10]}...")
        return is_valid
    except Exception as e:
        logger.error(f"Strava signature validation error: {e}")
        return False


# =========================
# ✅ STRAVA WEBHOOK VALIDATION
# =========================
@router.get("/strava")
async def strava_webhook_validation(request: Request):
    """
    Strava subscription verification endpoint.
    
    Strava sends GET request with hub.challenge parameter
    during initial webhook registration.
    """
    params = request.query_params
    hub_challenge = params.get("hub.challenge")

    if not hub_challenge:
        logger.warning("Strava webhook validation missing hub.challenge")
        return {"error": "Missing hub.challenge"}

    logger.info(f"Strava webhook validation request received")
    return {"hub.challenge": hub_challenge}


# =========================
# 📡 STRAVA EVENT HANDLER
# =========================
@router.post("/strava")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def strava_webhook_event(
    request: Request
):
    """
    Handles Strava webhook events (activity create/update).
    
    Flow:
    1. Validate webhook signature using STRAVA_SIGNING_SECRET
    2. Parse activity JSON
    3. Check for duplicates by strava_id
    4. Enqueue to data_sync queue (non-blocking)
    5. Return 200 OK immediately
    
    Strava sends:
    - X-Strava-Hook-Signature: HMAC-SHA256 signature
    - X-Strava-Hook-Id: Unique ID for this subscription
    """
    try:
        # Get raw body for signature validation
        raw_body = await request.body()
        
        # Get signature from header
        signature = request.headers.get("X-Strava-Hook-Signature", "")
        
        # Validate signature
        if not validate_strava_signature(raw_body, signature):
            logger.warning({
                "event": "strava_webhook_security_failure",
                "detail": "Invalid webhook signature"
            })
            return Response(status_code=status.HTTP_200_OK)
        
        logger.info("✅ Strava webhook signature validated")
        
        # Parse JSON payload
        data = await request.json()
        
        logger.info({
            "event": "strava_webhook_received",
            "aspect_type": data.get("aspect_type"),
            "object_type": data.get("object_type"),
            "object_id": data.get("object_id"),
            "owner_id": data.get("owner_id")
        })
        
        # Only process new/updated activities
        aspect_type = data.get("aspect_type")
        object_type = data.get("object_type")
        
        if object_type != "activity":
            logger.debug(f"Ignoring non-activity webhook: {object_type}")
            return Response(status_code=status.HTTP_200_OK)
        
        if aspect_type not in ["create", "update"]:
            logger.debug(f"Ignoring {aspect_type} aspect type")
            return Response(status_code=status.HTTP_200_OK)
        
        # Extract required fields
        athlete_id = data.get("owner_id")
        activity_id = data.get("object_id")
        
        if not athlete_id or not activity_id:
            logger.warning({
                "event": "strava_webhook_missing_data",
                "detail": "Missing athlete_id or activity_id",
                "data": data
            })
            return Response(status_code=status.HTTP_200_OK)
        
        logger.info(f"📡 Processing Strava {aspect_type} event for athlete {athlete_id}, activity {activity_id}")
        
        process_strava_webhook_event.delay(int(athlete_id), int(activity_id))
        
        logger.info({
            "event": "strava_webhook_queued",
            "athlete_id": athlete_id,
            "activity_id": activity_id
        })
        
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.exception({
            "event": "strava_webhook_processing_failed",
            "error": str(e)
        })
        return Response(status_code=status.HTTP_200_OK)
