# backend/strava_manager.py
import os
import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from dateutil import parser

from backend.database import SessionLocal
from backend.models import User, Activity, StravaToken, DailyReadiness

logger = logging.getLogger(__name__)

class StravaManager:
    def __init__(self):
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.base_url = "https://www.strava.com/api/v3"

    async def get_valid_token(self, db: Session, user_id: int) -> Optional[str]:
        token = db.query(StravaToken).filter_by(user_id=user_id).first()
        if not token:
            return None

        now = datetime.now(timezone.utc).timestamp()
        if now < (token.expires_at - 300):
            return token.access_token

        logger.info(f"🔄 Refreshing Strava access token for user {user_id}")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.strava.com/oauth/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": token.refresh_token
                },
                timeout=10
            )

        if resp.status_code != 200:
            logger.error(f"❌ Token refresh failed: {resp.text}")
            return None

        data = resp.json()
        token.access_token = data["access_token"]
        token.refresh_token = data["refresh_token"]
        token.expires_at = data["expires_at"]
        db.commit()
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
                max_heart_rate=act.get("max_heartrate")
            )
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
                except Exception as e:
                    logger.error(f"❌ Periodic activity sync failed for User {uid}: {str(e)}")

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

                res = await client.get(
                    f"{self.base_url}/athlete/activities",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"per_page": per_page_limit, "page": page},
                    timeout=15
                )

                if res.status_code != 200:
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

    async def handle_webhook(self, athlete_id: int, activity_id: int):
        db = SessionLocal()
        try:
            token_rec = db.query(StravaToken).filter_by(athlete_id=athlete_id).first()
            if not token_rec: return

            user = db.query(User).filter_by(id=token_rec.user_id).first()
            if not user: return

            token = await self.get_valid_token(db, user.id)
            if not token: return

            async with httpx.AsyncClient() as client_http:
                res = await client_http.get(
                    f"{self.base_url}/activities/{activity_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )

            if res.status_code != 200: return

            activity = res.json()
            self.bulk_save_activities(db, user.id, [activity])
            saved_act = db.query(Activity).filter_by(strava_id=activity_id).first()

            from backend.analytics import update_user_fitness_metrics
            update_user_fitness_metrics(db, user.id)

            workout_prompt = f"Analyze my completed workout: {saved_act.name} of {saved_act.distance_km} km. Detail my physiological cardiac cost and recovery priority."

            from backend.orchestration.coach_service import CoachService
            response = CoachService.generate(db=db, user_id=user.id, user_input=workout_prompt, activity_data=saved_act)

            if user.telegram_chat_id:
                from backend.notifications import send_telegram_message, send_telegram_buttons
                send_telegram_message(f"🏃‍♂️ *New Workout Logged:* {activity.get('name')} ({round(saved_act.distance_km, 2)} km)\n\n{response}", user.telegram_chat_id)
                send_telegram_buttons(f"How did the effort of *{activity.get('name')}* feel on a scale of 1 (Recovery) to 10 (Max Effort)?", ["RPE: 1-3 (Easy)", "RPE: 4-6 (Moderate)", "RPE: 7-8 (Hard)", "RPE: 9-10 (Max)"], user.telegram_chat_id)

        except Exception as e:
            logger.error(f"❌ Webhook handle failed: {str(e)}", exc_info=True)
        finally:
            db.close()

strava_manager = StravaManager()
