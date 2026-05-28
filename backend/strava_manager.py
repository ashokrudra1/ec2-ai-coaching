# backend/strava_manager.py
import os
import httpx
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from dateutil import parser

from backend.database import SessionLocal
from backend.models import User, Activity, StravaToken
from backend.orchestration.autonomous_planner import AutonomousPlanner
from backend.sports_science.monitoring import AthleteMonitoringService
from backend.sports_science.security_utils import decrypt_client_secret

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StravaCredentials:
    client_id: str
    client_secret: str


class StravaManager:
    def __init__(self):
        self.base_url = "https://www.strava.com/api/v3"

    def _get_system_credentials(self) -> StravaCredentials:
        client_id = os.getenv("STRAVA_CLIENT_ID")
        client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        if not client_id or not client_secret:
            logger.error("System Strava credentials are missing from environment")
            raise RuntimeError("System Strava credentials are not configured")
        return StravaCredentials(client_id=str(client_id), client_secret=str(client_secret))

    def _resolve_credentials_for_user(self, user: User) -> Tuple[StravaCredentials, bool]:
        if user.is_using_byok and user.strava_custom_client_id and user.strava_custom_client_secret_encrypted:
            try:
                decrypted_secret = decrypt_client_secret(user.strava_custom_client_secret_encrypted)
                return (
                    StravaCredentials(
                        client_id=str(user.strava_custom_client_id),
                        client_secret=decrypted_secret,
                    ),
                    True,
                )
            except (RuntimeError, ValueError) as exc:
                logger.error("BYOK credential resolution failed for user_id=%s: %s", user.id, exc)
        return self._get_system_credentials(), False

    async def _refresh_access_token(
        self,
        token: StravaToken,
        credentials: StravaCredentials,
    ) -> Optional[Dict]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://www.strava.com/oauth/token",
                    data={
                        "client_id": credentials.client_id,
                        "client_secret": credentials.client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": token.refresh_token,
                    },
                    timeout=10.0,
                )
        except httpx.TimeoutException:
            logger.error("Strava token refresh timed out for user_id=%s", token.user_id)
            return None
        except httpx.HTTPError as exc:
            logger.error("HTTP error during token refresh for user_id=%s: %s", token.user_id, exc)
            return None

        if resp.status_code != 200:
            logger.error("Token refresh failed for user_id=%s: %s", token.user_id, resp.text)
            return None

        try:
            return resp.json()
        except ValueError:
            logger.error("Strava token refresh returned invalid JSON for user_id=%s", token.user_id)
            return None

    async def get_valid_token(self, db: Session, user_id: int) -> Optional[str]:
        token = db.query(StravaToken).filter_by(user_id=user_id).first()
        if not token:
            return None
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            logger.warning("User context missing while resolving token for user_id=%s", user_id)
            return None

        now = datetime.now(timezone.utc).timestamp()
        if now < (token.expires_at - 300):
            return token.access_token

        credentials, using_byok = self._resolve_credentials_for_user(user)
        logger.info(
            "Refreshing Strava access token for user_id=%s using %s credentials",
            user_id,
            "BYOK" if using_byok else "system",
        )
        refreshed_payload = await self._refresh_access_token(token, credentials)
        if not refreshed_payload:
            return None

        try:
            token.access_token = refreshed_payload["access_token"]
            token.refresh_token = refreshed_payload["refresh_token"]
            token.expires_at = refreshed_payload["expires_at"]
            db.commit()
        except KeyError as exc:
            logger.error("Refresh payload missing expected field for user_id=%s: %s", user_id, exc)
            db.rollback()
            return None
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Database commit failed while saving refreshed token for user_id=%s", user_id)
            return None

        return token.access_token

    def bulk_save_activities(self, db: Session, user_id: int, activities: List[Dict]) -> int:
        if not activities:
            return 0

        incoming_ids = [int(act["id"]) for act in activities]
        existing = db.query(Activity.strava_id).filter(
            Activity.user_id == user_id,
            Activity.strava_id.in_(incoming_ids)
        ).all()
        existing_ids: Set[int] = {r[0] for r in existing}

        new_count = 0
        for act in activities:
            strava_id = int(act["id"])
            if strava_id in existing_ids:
                continue

            splits = act.get("splits_metric") or act.get("laps") or []
            new_act = Activity(
                user_id=user_id,
                strava_id=strava_id,
                name=act.get("name"),
                distance_km=act.get("distance", 0) / 1000,
                moving_time_min=act.get("moving_time", 0) / 60,
                elapsed_time_min=act.get("elapsed_time", 0) / 60,
                type=act.get("type"),
                start_date_utc=parser.parse(act.get("start_date")),
                avg_heart_rate=act.get("average_heartrate"),
                max_heart_rate=act.get("max_heartrate"),
                avg_cadence=act.get("average_cadence"),
                total_elevation_gain=act.get("total_elevation_gain") or 0.0,
                splits=splits,
            )
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                AthleteMonitoringService.process_activity(db, new_act, user)
            db.add(new_act)
            new_count += 1

        if new_count > 0:
            db.commit()
            logger.info(f"💾 Bulk saved {new_count} new runs for user_id {user_id}")
        return new_count

    async def sync_recent(self):
        """Refactored context lifecycle execution map. Protects pool boundaries from exhaustion."""
        with SessionLocal() as db:
            users = db.query(User.id).all()
            user_ids = [u.id for u in users]

        async with httpx.AsyncClient() as client:
            for uid in user_ids:
                with SessionLocal() as db:
                    token = await self.get_valid_token(db, uid)
                if not token:
                    continue

                try:
                    res = await client.get(
                        f"{self.base_url}/athlete/activities",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"per_page": 10},
                        timeout=10
                    )
                    if res.status_code == 200:
                        with SessionLocal() as db:
                            self.bulk_save_activities(db, uid, res.json())
                    else:
                        logger.error("Periodic sync fetch failed for user_id=%s status=%s", uid, res.status_code)
                except httpx.TimeoutException:
                    logger.error("Periodic sync timed out for user_id=%s", uid)
                except httpx.HTTPError as exc:
                    logger.error("Periodic sync HTTP error for user_id=%s: %s", uid, exc)

    async def backfill(self, user_id: int, max_activities_limit: int = 600) -> int:
        page = 1
        total_saved = 0
        per_page_limit = 200

        async with httpx.AsyncClient() as client:
            while total_saved < max_activities_limit:
                with SessionLocal() as db:
                    token = await self.get_valid_token(db, user_id)
                if not token:
                    break

                try:
                    res = await client.get(
                        f"{self.base_url}/athlete/activities",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"per_page": per_page_limit, "page": page},
                        timeout=15
                    )
                except httpx.TimeoutException:
                    logger.error("Backfill page fetch timed out for user_id=%s page=%s", user_id, page)
                    break
                except httpx.HTTPError as exc:
                    logger.error("Backfill HTTP error for user_id=%s page=%s: %s", user_id, page, exc)
                    break

                if res.status_code != 200:
                    logger.error("Backfill fetch failed for user_id=%s page=%s status=%s", user_id, page, res.status_code)
                    break

                activities = res.json()
                if not activities:
                    break

                with SessionLocal() as db:
                    new_saves = self.bulk_save_activities(db, user_id, activities)
                total_saved += new_saves

                if len(activities) < per_page_limit:
                    break
                page += 1

        return total_saved

    async def handle_webhook(self, athlete_id: int, activity_id: int, user_id: Optional[int] = None):
        db = SessionLocal()
        try:
            resolved_user_id = user_id
            if resolved_user_id is None:
                token_rec = db.query(StravaToken).filter_by(strava_athlete_id=athlete_id).first()
                if not token_rec:
                    logger.warning("No token record found for athlete_id=%s", athlete_id)
                    return
                resolved_user_id = token_rec.user_id

            user = db.query(User).filter_by(id=resolved_user_id).first()
            if not user:
                logger.warning("No user found for webhook athlete_id=%s user_id=%s", athlete_id, resolved_user_id)
                return

            token = await self.get_valid_token(db, user.id)
            if not token:
                logger.warning("Unable to resolve valid token for webhook user_id=%s", user.id)
                return

            async with httpx.AsyncClient() as client_http:
                res = await client_http.get(
                    f"{self.base_url}/activities/{activity_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )

            if res.status_code != 200:
                logger.error("Webhook activity fetch failed for user_id=%s status=%s", user.id, res.status_code)
                return

            activity = res.json()
            self.bulk_save_activities(db, user.id, [activity])
            saved_act = db.query(Activity).filter_by(strava_id=activity_id).first()

            workout_prompt = f"Analyze my completed workout: {saved_act.name} of {saved_act.distance_km} km. Detail my physiological cardiac cost and recovery priority."

            from backend.orchestration.coach_service import CoachService
            response = CoachService.generate(db=db, user_id=user.id, user_input=workout_prompt, activity_data=saved_act)

            if user.telegram_chat_id:
                from backend.notifications import send_telegram_message, send_telegram_buttons
                send_telegram_message(f"🏃‍♂️ *New Workout Logged:* {activity.get('name')} ({round(saved_act.distance_km, 2)} km)\n\n{response}", user.telegram_chat_id)
                send_telegram_buttons(f"How did the effort of *{activity.get('name')}* feel on a scale of 1 (Recovery) to 10 (Max Effort)?", ["RPE: 1-3 (Easy)", "RPE: 4-6 (Moderate)", "RPE: 7-8 (Hard)", "RPE: 9-10 (Max)"], user.telegram_chat_id)
                intervention_hint = AutonomousPlanner.intervention_hint_from_activity(activity, float(user.tsb or 0.0))
                if intervention_hint:
                    send_telegram_message(f"🛡️ *Live Intervention Cue:*\n{intervention_hint}", user.telegram_chat_id)

        except httpx.TimeoutException:
            logger.error("Webhook activity fetch timed out for athlete_id=%s activity_id=%s", athlete_id, activity_id)
        except httpx.HTTPError as exc:
            logger.error("Webhook HTTP error for athlete_id=%s activity_id=%s: %s", athlete_id, activity_id, exc)
        except ValueError as exc:
            logger.error("Webhook payload/processing validation failed: %s", exc)
        except Exception:
            logger.exception("Webhook handling failed for athlete_id=%s activity_id=%s", athlete_id, activity_id)
        finally:
            db.close()

strava_manager = StravaManager()
