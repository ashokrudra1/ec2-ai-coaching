"""
Strava OAuth Automation Handler
Manages Strava OAuth flow and historical activity sync
Fully automated after payment confirmation
"""
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Optional
import httpx
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import User, StravaToken
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class StravaOAuthManager:
    """
    Handles Strava OAuth flow automation
    """

    def __init__(self):
        self.client_id = settings.STRAVA_CLIENT_ID
        self.client_secret = settings.STRAVA_CLIENT_SECRET
        self.oauth_url = "https://www.strava.com/oauth/authorize"
        self.token_url = "https://www.strava.com/oauth/token"
        self.api_url = "https://www.strava.com/api/v3"

    def generate_oauth_link(self, state: str, chat_id: str, redirect_uri: str) -> str:
        """
        Generate Strava OAuth authorization link
        state: CSRF token (chat_id)
        redirect_uri: Where Strava redirects after auth
        """
        scopes = "read,read_all,activity:read_all"

        oauth_link = (
            f"{self.oauth_url}?"
            f"client_id={self.client_id}"
            f"&response_type=code"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scopes}"
            f"&state={state}"
        )

        return oauth_link

    async def exchange_code_for_token(self, code: str, chat_id: str) -> Dict:
        """
        Exchange OAuth code for access token
        Called by callback endpoint after user authorizes
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret.get_secret_value(),
                        "code": code,
                        "grant_type": "authorization_code",
                    },
                    timeout=10,
                )

            if response.status_code != 200:
                logger.error(f"❌ Token exchange failed: {response.text}")
                return {"success": False, "error": response.text}

            data = response.json()

            athlete = data.get("athlete", {})
            access_token = data["access_token"]
            refresh_token = data.get("refresh_token")
            expires_at = data.get("expires_at")

            logger.info(f"✅ Strava OAuth successful for athlete: {athlete.get('id')}")

            return {
                "success": True,
                "athlete_id": athlete.get("id"),
                "athlete_name": f"{athlete.get('firstname')} {athlete.get('lastname')}",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "profile_picture": athlete.get("profile_medium"),
            }

        except Exception as e:
            logger.error(f"❌ OAuth token exchange error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def save_strava_token(self, db: Session, user_id: int, token_data: Dict) -> bool:
        """
        Save Strava access token and athlete ID to database
        """
        try:
            # Check if token already exists
            existing = db.query(StravaToken).filter_by(user_id=user_id).first()

            if existing:
                existing.access_token = token_data["access_token"]
                existing.refresh_token = token_data.get("refresh_token")
                existing.expires_at = token_data.get("expires_at")
            else:
                strava_token = StravaToken(
                    user_id=user_id,
                    strava_athlete_id=token_data["athlete_id"],
                    access_token=token_data["access_token"],
                    refresh_token=token_data.get("refresh_token"),
                    expires_at=token_data.get("expires_at"),
                )
                db.add(strava_token)

            # Update user profile
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                user.strava_athlete_id = token_data["athlete_id"]
                user.last_sync_at = datetime.now(timezone.utc)

            db.commit()
            logger.info(f"✅ Strava token saved for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Token save error: {e}")
            db.rollback()
            return False

    async def get_historical_activities(
        self, access_token: str, athlete_id: int, limit: int = 200
    ) -> Dict:
        """
        Fetch all historical activities from Strava API
        Returns last `limit` activities (paginated)
        """
        try:
            all_activities = []
            page = 1
            per_page = 30

            async with httpx.AsyncClient() as client:
                while True:
                    headers = {"Authorization": f"Bearer {access_token}"}
                    params = {
                        "page": page,
                        "per_page": per_page,
                    }

                    response = await client.get(
                        f"{self.api_url}/athlete/activities",
                        headers=headers,
                        params=params,
                        timeout=10,
                    )

                    if response.status_code != 200:
                        logger.error(f"❌ Activity fetch failed: {response.text}")
                        return {"success": False, "error": response.text}

                    activities = response.json()
                    if not activities:
                        break

                    all_activities.extend(activities)

                    if len(all_activities) >= limit:
                        break

                    page += 1

            logger.info(f"✅ Fetched {len(all_activities)} historical activities for athlete {athlete_id}")

            return {
                "success": True,
                "count": len(all_activities),
                "activities": all_activities[:limit],
            }

        except Exception as e:
            logger.error(f"❌ Historical activity fetch error: {e}", exc_info=True)
            return {"success": False, "error": str(e), "activities": []}

    async def refresh_access_token(self, db: Session, user_id: int) -> Optional[str]:
        """
        Refresh expired Strava access token
        """
        try:
            token_record = db.query(StravaToken).filter_by(user_id=user_id).first()

            if not token_record:
                logger.warning(f"❌ No Strava token found for user {user_id}")
                return None

            # Check if token is expired
            now = datetime.now(timezone.utc).timestamp()
            if now < (token_record.expires_at - 300):
                return token_record.access_token  # Token still valid

            logger.info(f"🔄 Refreshing Strava token for user {user_id}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret.get_secret_value(),
                        "grant_type": "refresh_token",
                        "refresh_token": token_record.refresh_token,
                    },
                    timeout=10,
                )

            if response.status_code != 200:
                logger.error(f"❌ Token refresh failed: {response.text}")
                return None

            data = response.json()
            token_record.access_token = data["access_token"]
            token_record.refresh_token = data.get("refresh_token", token_record.refresh_token)
            token_record.expires_at = data.get("expires_at")

            db.commit()
            logger.info(f"✅ Token refreshed for user {user_id}")
            return data["access_token"]

        except Exception as e:
            logger.error(f"❌ Token refresh error: {e}")
            return None


class StravaIntegrationFlow:
    """
    Complete Strava integration flow for new users
    """

    def __init__(self):
        self.oauth_manager = StravaOAuthManager()

    async def initiate_strava_auth(self, chat_id: str, redirect_uri: str) -> Dict:
        """
        Step 1: Generate OAuth link for user
        """
        try:
            oauth_link = self.oauth_manager.generate_oauth_link(
                state=chat_id,
                chat_id=chat_id,
                redirect_uri=redirect_uri,
            )

            return {
                "success": True,
                "oauth_link": oauth_link,
                "message": "Click the link to authorize Strava",
            }

        except Exception as e:
            logger.error(f"❌ OAuth initiation error: {e}")
            return {"success": False, "error": str(e)}

    async def complete_strava_auth(
        self, db: Session, user_id: int, code: str, chat_id: str
    ) -> Dict:
        """
        Step 2: Exchange code for token and save
        """
        try:
            # Exchange code for token
            token_result = await self.oauth_manager.exchange_code_for_token(code, chat_id)

            if not token_result["success"]:
                return token_result

            # Save token to database
            saved = await self.oauth_manager.save_strava_token(db, user_id, token_result)

            if not saved:
                return {"success": False, "error": "Failed to save token"}

            return {
                "success": True,
                "athlete_id": token_result["athlete_id"],
                "athlete_name": token_result["athlete_name"],
                "message": "Strava connected successfully!",
            }

        except Exception as e:
            logger.error(f"❌ Auth completion error: {e}")
            return {"success": False, "error": str(e)}

    async def sync_historical_activities(
        self, db: Session, user_id: int
    ) -> Dict:
        """
        Step 3: Fetch and store all historical activities
        """
        try:
            # Get Strava token
            token_record = db.query(StravaToken).filter_by(user_id=user_id).first()

            if not token_record:
                return {"success": False, "error": "No Strava token found"}

            # Fetch activities
            access_token = await self.oauth_manager.refresh_access_token(db, user_id)
            if not access_token:
                access_token = token_record.access_token

            activities_result = await self.oauth_manager.get_historical_activities(
                access_token, token_record.strava_athlete_id, limit=200
            )

            if not activities_result["success"]:
                return activities_result

            # TODO: Process and store activities (Phase 2)
            # - Parse each activity
            # - Extract metrics (TSS, pace, HR, etc.)
            # - Store in database
            # - Calculate CTL/ATL/TSB

            return {
                "success": True,
                "activities_count": activities_result["count"],
                "message": f"Synced {activities_result['count']} activities",
                "next_step": "Calculating metrics...",
            }

        except Exception as e:
            logger.error(f"❌ Activity sync error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def complete_registration(
        self, db: Session, user_id: int, registration_data: Dict
    ) -> Dict:
        """
        Complete entire registration flow after payment
        1. Exchange Strava code for token
        2. Save token to DB
        3. Fetch historical activities
        4. Calculate initial metrics
        """
        try:
            logger.info(f"Starting complete registration for user {user_id}")

            # Step 1: Save auth code
            if registration_data.get("strava_code"):
                auth_result = await self.complete_strava_auth(
                    db,
                    user_id,
                    registration_data["strava_code"],
                    registration_data.get("chat_id"),
                )

                if not auth_result["success"]:
                    return auth_result

            # Step 2: Sync activities
            sync_result = await self.sync_historical_activities(db, user_id)

            if not sync_result["success"]:
                logger.warning(f"Activity sync warning: {sync_result}")
                # Don't fail registration if sync has issues
                # It can be retried later

            return {
                "success": True,
                "message": "Registration complete! Your coach is ready.",
                "next_step": "First coaching message incoming...",
            }

        except Exception as e:
            logger.error(f"❌ Registration completion error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
