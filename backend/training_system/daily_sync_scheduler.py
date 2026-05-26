"""
Phase 4: Daily Automated Sync Loop & Real-Time Webhook Handler
Syncs activities daily, processes them, detects anomalies
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import User, Activity, PerformanceMetric
from backend.strava_manager import strava_manager
from backend.training_system.metrics_calculator import MetricsPipeline
from backend.notifications import send_telegram_message

logger = logging.getLogger(__name__)


class DailySyncScheduler:
    """
    Orchestrates daily 00:00 UTC syncs via Celery Beat
    """

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.trigger_daily_sync")
    def trigger_daily_sync():
        """
        Daily 00:00 UTC sync entrypoint.
        Syncs all active users' recent activities.
        """
        logger.info("🔄 Daily sync scheduler starting...")
        db = SessionLocal()
        try:
            active_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active",
                User.subscription_expiry > datetime.now(timezone.utc)
            ).all()

            logger.info(f"📊 Found {len(active_users)} active users for sync")

            for user in active_users:
                try:
                    DailySyncScheduler.sync_user_activities(db, user.id)
                except Exception as e:
                    logger.error(f"❌ Sync failed for user {user.id}: {e}")
                    continue

            logger.info("✅ Daily sync scheduler completed successfully")

        except Exception as e:
            logger.error(f"❌ Daily sync scheduler error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def sync_user_activities(db: Session, user_id: int) -> bool:
        """
        Sync recent activities for a single user.
        Flow: Fetch from Strava → Process → Update metrics → Detect anomalies
        """
        user = db.query(User).filter_by(id=user_id).first()
        if not user or not user.strava_athlete_id:
            return False

        try:
            logger.info(f"🏃 Syncing activities for user {user_id}...")

            # Step 1: Fetch recent activities from Strava (last 48 hours)
            activities = asyncio.run(
                strava_manager.sync_recent_activities(user_id, hours=48)
            )

            if not activities:
                logger.info(f"No new activities for user {user_id}")
                return True

            logger.info(f"📥 Fetched {len(activities)} new activities")

            # Step 2: Process each activity
            new_count = 0
            for activity_data in activities:
                if ActivityProcessor.process_activity(db, user_id, activity_data):
                    new_count += 1

            logger.info(f"✅ Processed {new_count} new activities")

            # Step 3: Recalculate user metrics
            MetricsPipeline.process_user_metrics(db, user_id)

            # Step 4: Check for anomalies
            anomalies = AnomalyDetector.check_anomalies(db, user_id)
            if anomalies:
                for anomaly in anomalies:
                    Alerter.send_anomaly_alert(db, user_id, anomaly)

            user.last_sync_at = datetime.now(timezone.utc)
            db.commit()

            return True

        except Exception as e:
            logger.error(f"❌ Sync error for user {user_id}: {e}", exc_info=True)
            return False


class ActivityProcessor:
    """
    Processes individual activities from Strava
    """

    @staticmethod
    def process_activity(db: Session, user_id: int, activity_data: Dict) -> bool:
        """
        Process single activity:
        - Check if already exists (by strava_id)
        - Create Activity record
        - Calculate TSS
        - Update performance metrics
        """
        try:
            strava_id = activity_data.get("id")
            
            # Check if already processed
            existing = db.query(Activity).filter_by(
                user_id=user_id,
                strava_activity_id=strava_id
            ).first()
            
            if existing:
                logger.debug(f"Activity {strava_id} already processed")
                return False

            # Extract activity data
            activity = Activity(
                user_id=user_id,
                strava_activity_id=strava_id,
                name=activity_data.get("name", "Activity"),
                sport_type=activity_data.get("type", "Run"),
                start_date_utc=activity_data.get("start_date", datetime.now(timezone.utc)),
                duration=activity_data.get("elapsed_time", 0),
                distance=activity_data.get("distance", 0) / 1000,  # Convert to km
                avg_hr=activity_data.get("average_heartrate", 0),
                max_hr=activity_data.get("max_heartrate", 0),
                calories=activity_data.get("calories", 0),
                elevation_gain=activity_data.get("total_elevation_gain", 0),
                commute=activity_data.get("commute", False),
                trainer=activity_data.get("trainer", False),
            )

            # Calculate TSS
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                activity.training_stress_score_tss = ActivityProcessor._calculate_tss(
                    activity, user
                )

            db.add(activity)
            db.commit()

            logger.info(f"✅ Processed activity: {activity.name} ({activity.distance:.1f} km)")
            return True

        except Exception as e:
            logger.error(f"❌ Activity processing error: {e}")
            db.rollback()
            return False

    @staticmethod
    def _calculate_tss(activity: Activity, user: User) -> float:
        """
        Calculate Training Stress Score using HR-based model.
        TSS = (IF^2) × hours × 100
        where IF = avg_hr / threshold_hr
        """
        try:
            if not activity.avg_hr or not activity.duration:
                return 0.0

            threshold_hr = user.physiological_twin.get("threshold_hr", 165)
            hours = activity.duration / 3600

            intensity_factor = activity.avg_hr / threshold_hr
            tss = (intensity_factor ** 2) * hours * 100

            return min(tss, 500)  # Cap at 500

        except Exception as e:
            logger.error(f"TSS calculation error: {e}")
            return 0.0


class AnomalyDetector:
    """
    Detects unusual performances that warrant coaching alerts
    """

    @staticmethod
    def check_anomalies(db: Session, user_id: int) -> List[Dict]:
        """
        Check for anomalies in recent activities.
        Returns list of anomalies found.
        """
        anomalies = []

        try:
            # Get last 7 days of activities
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent = db.query(Activity).filter(
                and_(
                    Activity.user_id == user_id,
                    Activity.start_date_utc >= seven_days_ago
                )
            ).order_by(Activity.start_date_utc.desc()).all()

            if len(recent) < 2:
                return []

            latest = recent[0]
            previous_7day_avg = sum(a.training_stress_score_tss for a in recent[1:]) / (len(recent) - 1)

            # Anomaly 1: Unusually high TSS (potential overtraining session)
            if latest.training_stress_score_tss > previous_7day_avg * 1.5 and previous_7day_avg > 0:
                anomalies.append({
                    "type": "high_tss",
                    "severity": "medium",
                    "message": f"Very high effort today ({latest.training_stress_score_tss:.0f} TSS) compared to usual ({previous_7day_avg:.0f}). Ensure adequate recovery.",
                    "activity_id": latest.id
                })

            # Anomaly 2: Unusually low pace on long run (might be injury/illness)
            if latest.distance > 15 and latest.sport_type == "Run":
                expected_pace = AnomalyDetector._get_expected_pace(db, user_id)
                if expected_pace:
                    actual_pace = latest.duration / (latest.distance * 60)  # min/km
                    if actual_pace > expected_pace * 1.2:  # 20% slower
                        anomalies.append({
                            "type": "unusual_pace",
                            "severity": "low",
                            "message": f"You ran slower than usual today. Feeling okay? Any pain or fatigue?",
                            "activity_id": latest.id
                        })

            # Anomaly 3: Very high HR for effort level
            if latest.avg_hr and latest.training_stress_score_tss:
                hr_to_tss_ratio = latest.avg_hr / latest.training_stress_score_tss
                baseline_ratio = AnomalyDetector._get_baseline_hr_tss_ratio(db, user_id)
                if baseline_ratio and hr_to_tss_ratio > baseline_ratio * 1.15:
                    anomalies.append({
                        "type": "elevated_hr",
                        "severity": "low",
                        "message": f"Your HR was elevated today ({latest.avg_hr:.0f} bpm). Could indicate fatigue or stress.",
                        "activity_id": latest.id
                    })

            logger.info(f"🔍 Found {len(anomalies)} anomalies for user {user_id}")
            return anomalies

        except Exception as e:
            logger.error(f"Anomaly detection error: {e}")
            return []

    @staticmethod
    def _get_expected_pace(db: Session, user_id: int) -> Optional[float]:
        """Get average pace from last 30 days of runs"""
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        activities = db.query(Activity).filter(
            and_(
                Activity.user_id == user_id,
                Activity.sport_type == "Run",
                Activity.start_date_utc >= thirty_days_ago,
                Activity.distance > 0
            )
        ).all()

        if not activities:
            return None

        avg_pace = sum(a.duration / a.distance for a in activities) / len(activities)
        return avg_pace

    @staticmethod
    def _get_baseline_hr_tss_ratio(db: Session, user_id: int) -> Optional[float]:
        """Get baseline HR/TSS ratio from last 30 days"""
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        activities = db.query(Activity).filter(
            and_(
                Activity.user_id == user_id,
                Activity.start_date_utc >= thirty_days_ago,
                Activity.avg_hr > 0,
                Activity.training_stress_score_tss > 0
            )
        ).all()

        if not activities:
            return None

        avg_ratio = sum(a.avg_hr / a.training_stress_score_tss for a in activities) / len(activities)
        return avg_ratio


class StravaWebhookHandler:
    """
    Handles real-time activity push from Strava
    """

    @staticmethod
    def handle_strava_webhook(event_data: Dict) -> bool:
        """
        Process real-time Strava webhook event.
        Called when athlete creates activity.
        """
        db = SessionLocal()
        try:
            object_type = event_data.get("object_type")
            aspect_type = event_data.get("aspect_type")
            owner_id = event_data.get("owner_id")  # Strava athlete ID

            if object_type != "activity" or aspect_type != "create":
                return True  # Ignore non-activity events

            logger.info(f"🔔 Real-time activity from Strava athlete {owner_id}")

            # Get user by strava_athlete_id
            user = db.query(User).filter_by(strava_athlete_id=str(owner_id)).first()
            if not user:
                logger.warning(f"User not found for Strava athlete {owner_id}")
                return False

            # Fetch full activity data from Strava
            activity_data = asyncio.run(
                strava_manager.get_activity_details(user.id, event_data.get("object_id"))
            )

            if not activity_data:
                logger.warning(f"Could not fetch activity details")
                return False

            # Process immediately
            ActivityProcessor.process_activity(db, user.id, activity_data)

            # Update metrics
            MetricsPipeline.process_user_metrics(db, user.id)

            # Send confirmation to user
            send_telegram_message(
                f"✅ <b>{activity_data.get('name', 'Activity')}</b> logged!\n"
                f"📊 {activity_data.get('distance', 0)/1000:.1f} km | "
                f"⏱️ {activity_data.get('elapsed_time', 0)//60} min",
                user.telegram_chat_id
            )

            logger.info(f"✅ Real-time sync completed for user {user.id}")
            return True

        except Exception as e:
            logger.error(f"❌ Strava webhook error: {e}", exc_info=True)
            return False
        finally:
            db.close()


class Alerter:
    """
    Sends alerts for anomalies and issues
    """

    @staticmethod
    def send_anomaly_alert(db: Session, user_id: int, anomaly: Dict) -> bool:
        """Send anomaly alert to user via Telegram"""
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            severity_emoji = {
                "critical": "🚨",
                "high": "⚠️",
                "medium": "⚡",
                "low": "ℹ️"
            }

            emoji = severity_emoji.get(anomaly.get("severity", "medium"), "📌")
            message = f"{emoji} {anomaly.get('message', 'Coaching note')}"

            send_telegram_message(message, user.telegram_chat_id)
            logger.info(f"✅ Anomaly alert sent to user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Alert sending error: {e}")
            return False
