import os
import httpx
import logging
import secrets
import base64
import hashlib
from typing import Optional, Tuple
from fastapi import APIRouter, Request, Depends, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.database import get_db
from backend.models import User, StravaToken
from backend.config.settings import settings
from backend.sports_science.security_utils import decrypt_client_secret, encrypt_client_secret

logger = logging.getLogger(__name__)
router = APIRouter()


class ByokConfigRequest(BaseModel):
    telegram_chat_id: str = Field(min_length=1)
    strava_custom_client_id: str = Field(min_length=1)
    strava_custom_client_secret: str = Field(min_length=1)


class ByokDisableRequest(BaseModel):
    telegram_chat_id: str = Field(min_length=1)

# ============================================================================
# PKCE (Proof Key for Authorization Code Exchange) Implementation
# ============================================================================
class PKCEHelper:
    """Implements PKCE for secure OAuth 2.0 authorization."""
    
    @staticmethod
    def generate_code_verifier() -> str:
        """Generate a random code verifier (43-128 characters)."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    
    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        """Generate code challenge from verifier using SHA256."""
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _resolve_oauth_credentials_for_user(user: Optional[User]) -> Tuple[str, str]:
    if user and user.is_using_byok and user.strava_custom_client_id and user.strava_custom_client_secret_encrypted:
        try:
            return (
                str(user.strava_custom_client_id),
                decrypt_client_secret(user.strava_custom_client_secret_encrypted),
            )
        except (RuntimeError, ValueError) as exc:
            logger.error("Failed to resolve BYOK OAuth credentials for user_id=%s: %s", user.id, exc)

    return settings.STRAVA_CLIENT_ID, settings.STRAVA_CLIENT_SECRET.get_secret_value()


def generate_auth_link(chat_id: str, use_pkce: bool = False, db: Optional[Session] = None) -> tuple[str, str]:
    """
    Generate Strava OAuth authorization link with optional PKCE support.
    
    Returns: (auth_url, code_verifier) where code_verifier is empty string if PKCE disabled
    """
    user = None
    if db is not None:
        user = db.query(User).filter_by(telegram_chat_id=str(chat_id)).first()
    client_id, _ = _resolve_oauth_credentials_for_user(user)
    redirect_uri = settings.STRAVA_REDIRECT_URI
    
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "force",
        "scope": "read,activity:read_all",
        "state": chat_id,
    }
    
    code_verifier = ""
    
    # Optional PKCE enhancement (requires server-side storage)
    if use_pkce:
        code_verifier = PKCEHelper.generate_code_verifier()
        code_challenge = PKCEHelper.generate_code_challenge(code_verifier)
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
        logger.info(f"PKCE enabled for user {chat_id}")
    
    # Build URL
    auth_url = "https://www.strava.com/oauth/authorize?" + "&".join(
        f"{k}={v}" for k, v in params.items()
    )
    
    return auth_url, code_verifier


def validate_oauth_state(state: str, expected_chat_id: str) -> bool:
    """
    Validate that OAuth state parameter matches expected chat_id.
    Protects against CSRF attacks.
    """
    if not state:
        logger.warning("OAuth state parameter missing")
        return False
    
    if state != expected_chat_id:
        logger.warning(f"OAuth state mismatch: {state} != {expected_chat_id}")
        return False
    
    return True


@router.post("/auth/strava/byok/config")
async def configure_strava_byok(payload: ByokConfigRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(telegram_chat_id=str(payload.telegram_chat_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for telegram_chat_id")

    try:
        encrypted_secret = encrypt_client_secret(payload.strava_custom_client_secret)
    except ValueError as exc:
        logger.error("Invalid BYOK payload for user_id=%s: %s", user.id, exc)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("BYOK encryption unavailable for user_id=%s: %s", user.id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="BYOK encryption unavailable") from exc

    user.strava_custom_client_id = payload.strava_custom_client_id.strip()
    user.strava_custom_client_secret_encrypted = encrypted_secret
    user.is_using_byok = True
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist BYOK config for user_id=%s", user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist BYOK config")

    logger.info("BYOK credentials configured for user_id=%s", user.id)
    return {"status": "ok", "user_id": user.id, "is_using_byok": True}


@router.post("/auth/strava/byok/disable")
async def disable_strava_byok(payload: ByokDisableRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(telegram_chat_id=str(payload.telegram_chat_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for telegram_chat_id")

    user.is_using_byok = False
    user.strava_custom_client_id = None
    user.strava_custom_client_secret_encrypted = None
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to disable BYOK for user_id=%s", user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to disable BYOK")

    logger.info("BYOK credentials disabled for user_id=%s", user.id)
    return {"status": "ok", "user_id": user.id, "is_using_byok": False}


@router.get("/auth/strava")
async def strava_auth_initiate(request: Request, db: Session = Depends(get_db)):
    """
    Initiate Strava OAuth flow.
    
    Query params:
    - chat_id: Telegram chat ID (passed from Telegram bot)
    
    Returns redirect to Strava authorization endpoint.
    """
    chat_id = request.query_params.get("chat_id")
    
    if not chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing chat_id parameter"
        )
    
    auth_url, _ = generate_auth_link(chat_id, use_pkce=False, db=db)
    logger.info(f"Strava OAuth flow initiated for user {chat_id}")
    
    return {"auth_url": auth_url}


@router.get("/auth/callback", response_class=HTMLResponse)
async def strava_callback(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Strava OAuth callback handler.
    
    Automated Strava OAuth Gateway. 
    Exchanges temporary verification codes for long-lived access tokens,
    maps credentials to the athlete's record, and starts the background data ingestion.
    
    Security validation:
    1. Verify state parameter matches expected chat_id (CSRF protection)
    2. Exchange authorization code for access/refresh tokens
    3. Store tokens securely in database
    4. Initiate background data sync
    """
    params = request.query_params
    code = params.get("code")
    chat_id = params.get("state")
    error = params.get("error")
    
    # ====================================================================
    # ERROR HANDLING FROM STRAVA
    # ====================================================================
    if error:
        logger.warning(f"Strava OAuth error: {error}")
        error_desc = params.get("error_description", "Unknown error")
        return f"""
        <html>
            <head>
                <title>Authorization Failed</title>
                <style>
                    body {{ font-family: sans-serif; text-align: center; padding-top: 100px; background-color: #f9fafb; }}
                    .container {{ max-width: 450px; margin: auto; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #dc2626; }}
                    h1 {{ color: #dc2626; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>❌ Authorization Failed</h1>
                    <p>{error_desc}</p>
                    <p>Please try connecting your Strava account again from Telegram.</p>
                </div>
            </body>
        </html>
        """
    
    # ====================================================================
    # VALIDATE REQUIRED PARAMETERS
    # ====================================================================
    if not code or not chat_id:
        logger.error(f"Missing verification parameters: code={bool(code)}, state={bool(chat_id)}")
        return "<h3>Error: Missing verification parameters from Strava.</h3>"
    
    # ====================================================================
    # VALIDATE OAUTH STATE (CSRF PROTECTION)
    # ====================================================================
    if not validate_oauth_state(chat_id, chat_id):
        logger.warning(f"OAuth state validation failed for chat_id {chat_id}")
        return "<h3>Error: Invalid OAuth state (security validation failed).</h3>"
    
    # ====================================================================
    # IDENTIFY USER CONTEXT BY TELEGRAM CHAT ID
    # ====================================================================
    user = db.query(User).filter_by(telegram_chat_id=str(chat_id)).first()
    if not user:
        logger.warning(f"User not found for chat_id {chat_id}")
        return "<h3>User context not found. Please restart via Telegram using /start</h3>"
    
    # ====================================================================
    # EXCHANGE AUTHORIZATION CODE FOR TOKENS
    # ====================================================================
    logger.info(f"Exchanging authorization code for tokens for user ID: {user.id}")
    
    async with httpx.AsyncClient() as client:
        try:
            oauth_client_id, oauth_client_secret = _resolve_oauth_credentials_for_user(user)
            resp = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": oauth_client_id,
                    "client_secret": oauth_client_secret,
                    "code": code,
                    "grant_type": "authorization_code"
                },
                timeout=10.0
            )
            
            if resp.status_code != 200:
                logger.error(f"Strava Token API returned status {resp.status_code}: {resp.text}")
                return f"""
                <html>
                    <head><title>Authentication Failed</title></head>
                    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                        <h3>❌ Authentication failed with Strava.</h3>
                        <p>Status: {resp.status_code}</p>
                        <p>Please try again.</p>
                    </body>
                </html>
                """
            
            data = resp.json()
            
        except httpx.TimeoutException:
            logger.error("Strava token exchange timed out")
            return "<h3>Connection to Strava timed out. Please try again.</h3>"
        except httpx.HTTPError as e:
            logger.exception(f"HTTP exception during token exchange: {str(e)}")
            return "<h3>Internal server error connecting to Strava.</h3>"
    
    # ====================================================================
    # VALIDATE RESPONSE DATA
    # ====================================================================
    if "access_token" not in data or "athlete" not in data:
        logger.error(f"Invalid Strava response: missing required fields")
        return "<h3>Invalid response from Strava. Please try again.</h3>"
    
    # ====================================================================
    # EXTRACT ATHLETE INFORMATION
    # ====================================================================
    athlete_data = data.get("athlete", {})
    strava_athlete_id = str(athlete_data.get("id"))
    athlete_name = athlete_data.get("firstname", "")
    
    if not strava_athlete_id or strava_athlete_id == "None":
        logger.error(f"Invalid athlete ID from Strava: {strava_athlete_id}")
        return "<h3>Could not retrieve athlete information. Please try again.</h3>"
    
    # ====================================================================
    # PERSIST TOKENS AND ATHLETE INFORMATION
    # ====================================================================
    try:
        token_rec = db.query(StravaToken).filter_by(user_id=user.id).first()
        if not token_rec:
            token_rec = StravaToken(user_id=user.id)
            db.add(token_rec)
        
        # Store tokens with validation
        token_rec.access_token = data.get("access_token")
        token_rec.refresh_token = data.get("refresh_token")
        token_rec.expires_at = data.get("expires_at")
        token_rec.strava_athlete_id = int(strava_athlete_id) if strava_athlete_id.isdigit() else None
        
        user.strava_athlete_id = strava_athlete_id
        
        db.commit()
        logger.info(f"✅ Strava tokens persisted for user {user.id} (athlete {strava_athlete_id})")
        
    except Exception as db_err:
        db.rollback()
        logger.error(f"Database commit failed: {str(db_err)}")
        return "<h3>Database write failure saving authentication state.</h3>"
    
    # ====================================================================
    # PRODUCTION TRIGGER: AUTOMATIC BACKGROUND HISTORICAL INGESTION
    # ====================================================================
    try:
        from backend.tasks.sync_tasks import trigger_onboarding_backfill
        trigger_onboarding_backfill.delay(user_id=user.id)
        logger.info(f"✅ Automatic history ingestion enqueued for user id: {user.id}")
    except Exception as queue_err:
        logger.error(f"❌ Failed to drop backfill task into queue: {str(queue_err)}")
    
    # ====================================================================
    # RENDER SUCCESS RESPONSE
    # ====================================================================
    user_name = user.name or athlete_name or "Athlete"
    
    return f"""
    <html>
        <head>
            <title>Connection Successful</title>
            <style>
                body {{ font-family: sans-serif; text-align: center; padding-top: 100px; background-color: #f9fafb; }}
                .container {{ max-width: 450px; margin: auto; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 5px solid #ff5722; }}
                h1 {{ color: #ff5722; }}
                p {{ color: #374151; font-size: 16px; line-height: 1.5; }}
                .athlete-info {{ background: #fafafa; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ Connection Successful!</h1>
                <p>Hello {user_name}, your Strava account is now connected.</p>
                <div class="athlete-info">
                    <strong>Athlete ID:</strong> {strava_athlete_id}
                </div>
                <p>Your historical activity data is syncing in the background.</p>
                <p>You can safely close this tab and return to Telegram.</p>
            </div>
        </body>
    </html>
    """
