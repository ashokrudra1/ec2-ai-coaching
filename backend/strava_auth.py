import os
import httpx
import logging
from fastapi import APIRouter, Request, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, StravaToken

logger = logging.getLogger(__name__)
router = APIRouter()

def generate_auth_link(chat_id: str) -> str:
    client_id = os.getenv("STRAVA_CLIENT_ID")
    redirect_uri = os.getenv("STRAVA_REDIRECT_URI")
    return (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&approval_prompt=force"
        f"&scope=read,activity:read_all"
        f"&state={chat_id}"
    )

@router.get("/auth/callback", response_class=HTMLResponse)
async def strava_callback(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Automated Strava OAuth Gateway. 
    Exchanges temporary verification codes for long-lived access tokens,
    maps credentials to the athlete's record, and starts the background data ingestion.
    """
    params = request.query_params
    code = params.get("code")
    chat_id = params.get("state")

    if not code or not chat_id:
        return "<h3>Error: Missing verification parameters from Strava.</h3>"

    # Identify user context by the Telegram chat ID passed through the state parameter
    user = db.query(User).filter_by(telegram_chat_id=str(chat_id)).first()
    if not user:
        return "<h3>User context not found. Please restart via Telegram using /start</h3>"

    # Execute non-blocking async OAuth key exchange with Strava API
    logger.info(f"Exchanging authorization code for tokens for user ID: {user.id}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": os.getenv("STRAVA_CLIENT_ID"),
                    "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
                    "code": code,
                    "grant_type": "authorization_code"
                },
                timeout=10.0
            )
            if resp.status_code != 200:
                logger.error(f"Strava Token API returned status {resp.status_code}: {resp.text}")
                return "<h3>Authentication failed with Strava. Please try again.</h3>"
            
            data = resp.json()
        except Exception as e:
            logger.exception(f"Exception during token exchange: {str(e)}")
            return "<h3>Internal server error connecting to Strava.</h3>"

    athlete_data = data.get("athlete", {})
    strava_athlete_id = str(athlete_data.get("id"))

    # Upsert token credentials into the database
    token_rec = db.query(StravaToken).filter_by(user_id=user.id).first()
    if not token_rec:
        token_rec = StravaToken(user_id=user.id)
        db.add(token_rec)

    token_rec.access_token = data["access_token"]
    token_rec.refresh_token = data["refresh_token"]
    token_rec.expires_at = data["expires_at"]
    token_rec.athlete_id = int(strava_athlete_id) if strava_athlete_id.isdigit() else None

    user.strava_athlete_id = strava_athlete_id
    
    try:
        db.commit()
        logger.info(f"Successfully saved Strava tokens for user {user.id}")
    except Exception as db_err:
        db.rollback()
        logger.error(f"Database commit failed: {str(db_err)}")
        return "<h3>Database write failure saving authentication state.</h3>"

    # =========================================================================
    # PRODUCTION TRIGGER: AUTOMATIC BACKGROUND HISTORICAL INGESTION
    # Hands the processing off to Celery instantly to avoid browser timeouts.
    # =========================================================================
    try:
        from backend.tasks.sync_tasks import trigger_onboarding_backfill
        trigger_onboarding_backfill.delay(user_id=user.id)
        logger.info(f"✅ Automatic history ingestion enqueued for user id: {user.id}")
    except Exception as queue_err:
        logger.error(f"❌ Failed to drop backfill task into queue: {str(queue_err)}")

    # Render confirmation view back to client browser layout
    return f"""
    <html>
        <head>
            <title>Connection Successful</title>
            <style>
                body {{ font-family: sans-serif; text-align: center; padding-top: 100px; background-color: #f9fafb; }}
                .container {{ max-width: 450px; margin: auto; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #ff5722; }}
                h1 {{ color: #ff5722; }}
                p {{ color: #374151; font-size: 16px; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Connection Successful!</h1>
                <p>Hello {user.name or 'Athlete'}, your account is fully connected.</p>
                <p>Your history is syncing automatically in the background. You can safely close this tab now and return to Telegram.</p>
            </div>
        </body>
    </html>
    """
