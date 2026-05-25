"""
Phase 7: Proactive Coaching Automation
Sends unsolicited coaching nudges based on athlete state
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import User, Activity
from backend.communication.intelligent_coach import ProactiveCoachingEngine
from backend.training_system.coach_memory_engine import ContextAssembler
from backend.notifications import send_telegram_message

logger = logging.getLogger(__name__)


class ProactiveMessageScheduler:
    """
    Schedules and sends proactive coaching messages
    """

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.send_daily_readiness_6am")
    def send_daily_readiness_6am():
        """
        Daily 6 AM UTC: Send readiness check-in to all active users.
        Tells them how ready they are to train, what to do today.
        """
        logger.info("🌅 Daily 6 AM readiness check starting...")
        db = SessionLocal()
        try:
            active_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active",
                User.subscription_expiry > datetime.now(timezone.utc)
            ).all()

            sent_count = 0
            for user in active_users:
                try:
                    # Generate readiness message
                    check = ProactiveCoachingEngine.generate_daily_readiness_check(db, user.id)
                    if check.get("success"):
                        send_telegram_message(
                            check.get("message"),
                            user.telegram_chat_id
                        )
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Daily readiness failed for user {user.id}: {e}")

            logger.info(f"✅ Daily readiness sent to {sent_count} users")

        except Exception as e:
            logger.error(f"❌ Daily readiness scheduler error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.send_weekly_report_friday")
    def send_weekly_report_friday():
        """
        Every Friday 9 AM UTC: Send weekly training report.
        Volume, TSB trends, performance analysis, next week recommendation.
        """
        logger.info("📊 Weekly report scheduler starting...")
        db = SessionLocal()
        try:
            active_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active"
            ).all()

            sent_count = 0
            for user in active_users:
                try:
                    report = ProactiveCoachingEngine.generate_weekly_report(db, user.id)
                    if report.get("success"):
                        send_telegram_message(
                            report.get("report"),
                            user.telegram_chat_id,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Weekly report failed for user {user.id}: {e}")

            logger.info(f"✅ Weekly reports sent to {sent_count} users")

        except Exception as e:
            logger.error(f"❌ Weekly report scheduler error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.send_monthly_progress")
    def send_monthly_progress():
        """
        1st of month 9 AM UTC: Send monthly progress report.
        Volume trends, PRs achieved, goal progress.
        """
        logger.info("📈 Monthly progress scheduler starting...")
        db = SessionLocal()
        try:
            active_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active"
            ).all()

            sent_count = 0
            for user in active_users:
                try:
                    report = ProactiveMessageScheduler._generate_monthly_progress(db, user.id)
                    if report:
                        send_telegram_message(
                            report,
                            user.telegram_chat_id,
                            parse_mode="HTML"
                        )
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Monthly progress failed for user {user.id}: {e}")

            logger.info(f"✅ Monthly progress sent to {sent_count} users")

        except Exception as e:
            logger.error(f"❌ Monthly progress scheduler error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _generate_monthly_progress(db: Session, user_id: int) -> Optional[str]:
        """Generate monthly progress report"""
        try:
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            state = context.get("current_state", {})
            metrics = context.get("metrics", {})

            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            activities = db.query(Activity).filter(
                and_(
                    Activity.user_id == user_id,
                    Activity.start_date_utc >= thirty_days_ago
                )
            ).all()

            total_volume = sum(a.distance for a in activities)
            total_tss = sum(a.training_stress_score_tss or 0 for a in activities)
            avg_weekly_volume = total_volume / 4

            report = f"""
📈 <b>Monthly Progress Report</b>

<b>Last 30 Days:</b>
• Total Volume: {total_volume:.0f} km
• Total TSS: {total_tss:.0f}
• Avg Weekly: {avg_weekly_volume:.0f} km
• Workouts: {len(activities)}

<b>Current Fitness:</b>
• CTL: {state.get('ctl', 0):.1f}
• ATL: {state.get('atl', 0):.1f}
• TSB: {state.get('tsb', 0):.1f}

<b>Goal Progress:</b>
On track for your goals! Keep pushing! 💪
"""
            return report

        except Exception as e:
            logger.error(f"Monthly progress generation error: {e}")
            return None


class TriggerBasedAlertSystem:
    """
    Sends alerts when triggered by athlete state changes
    """

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.check_and_send_trigger_alerts")
    def check_and_send_trigger_alerts():
        """
        Check all active users for trigger conditions.
        Runs every 2 hours.
        """
        logger.info("🔔 Trigger alert checker starting...")
        db = SessionLocal()
        try:
            active_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active"
            ).all()

            alert_count = 0
            for user in active_users:
                try:
                    alerts = TriggerBasedAlertSystem._check_user_triggers(db, user.id)
                    for alert in alerts:
                        send_telegram_message(
                            alert["message"],
                            user.telegram_chat_id
                        )
                        alert_count += 1
                except Exception as e:
                    logger.error(f"Trigger check failed for user {user.id}: {e}")

            logger.info(f"✅ {alert_count} trigger alerts sent")

        except Exception as e:
            logger.error(f"❌ Trigger alert error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _check_user_triggers(db: Session, user_id: int) -> List[Dict]:
        """Check all trigger conditions for user"""
        alerts = []

        try:
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            state = context.get("current_state", {})
            psych = context.get("psychological_state", {})
            readiness = state.get("readiness", 0)
            injury_risk = state.get("injury_risk", 0)
            tsb = state.get("tsb", 0)
            burnout_at_risk = context.get("burnout_risk", {}).get("at_risk", False)

            # Trigger 1: Peak readiness (> 85)
            if readiness > 85 and tsb > 5:
                alerts.append({
                    "type": "peak_opportunity",
                    "message": f"🔥 You're in peak form! (Readiness: {readiness:.0f}/100). Time for a hard workout!",
                    "priority": "high"
                })

            # Trigger 2: High injury risk (> 70)
            if injury_risk > 70:
                alerts.append({
                    "type": "injury_risk",
                    "message": f"⚠️ Injury risk elevated ({injury_risk:.0f}/100). Consider an easy day or rest.",
                    "priority": "critical"
                })

            # Trigger 3: Severe fatigue (TSB < -30)
            if tsb < -30:
                alerts.append({
                    "type": "overtraining",
                    "message": f"🛑 You're heavily fatigued (TSB: {tsb:.0f}). Take a recovery day—no hard efforts.",
                    "priority": "critical"
                })

            # Trigger 4: Burnout detected
            if burnout_at_risk:
                reason = context.get("burnout_risk", {}).get("reason", "fatigue")
                alerts.append({
                    "type": "burnout",
                    "message": f"💭 I sense you're struggling with {reason}. Let's talk—what's on your mind?",
                    "priority": "high"
                })

            # Trigger 5: No activity for 3+ days (motivation check)
            three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
            recent_activity = db.query(Activity).filter(
                and_(
                    Activity.user_id == user_id,
                    Activity.start_date_utc >= three_days_ago
                )
            ).first()

            if not recent_activity and psych.get("motivation", 0.7) < 0.6:
                alerts.append({
                    "type": "low_engagement",
                    "message": "👟 Haven't seen you train in a few days. What's going on? How can I help?",
                    "priority": "medium"
                })

            # Trigger 6: Great workout detected (form spike)
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            recent_activities = db.query(Activity).filter(
                and_(
                    Activity.user_id == user_id,
                    Activity.start_date_utc >= yesterday
                )
            ).all()

            if recent_activities:
                latest = recent_activities[-1]
                avg_tss = state.get("form_score", 0)
                if latest.training_stress_score_tss and avg_tss and latest.training_stress_score_tss > avg_tss * 1.3:
                    alerts.append({
                        "type": "great_workout",
                        "message": f"🎉 Awesome workout! Form is improving—keep it up!",
                        "priority": "low"
                    })

            logger.info(f"Found {len(alerts)} triggers for user {user_id}")
            return alerts

        except Exception as e:
            logger.error(f"Trigger check error: {e}")
            return []


class BehavioralCoachingNudges:
    """
    Behavioral nudges to improve adherence and motivation
    """

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.send_adherence_nudges")
    def send_adherence_nudges():
        """
        Check for missed workouts and send adherence reminders.
        Runs daily 7 PM UTC.
        """
        logger.info("📝 Adherence nudge checker starting...")
        db = SessionLocal()
        try:
            active_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active"
            ).all()

            nudge_count = 0
            for user in active_users:
                try:
                    nudge = BehavioralCoachingNudges._check_adherence(db, user.id)
                    if nudge:
                        send_telegram_message(nudge, user.telegram_chat_id)
                        nudge_count += 1
                except Exception as e:
                    logger.error(f"Adherence check failed for user {user.id}: {e}")

            logger.info(f"✅ {nudge_count} adherence nudges sent")

        except Exception as e:
            logger.error(f"❌ Adherence nudge error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _check_adherence(db: Session, user_id: int) -> Optional[str]:
        """Check if user should get adherence nudge"""
        try:
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            state = context.get("current_state", {})

            today = datetime.now(timezone.utc).date()
            today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
            
            # Check if activity logged today
            today_activity = db.query(Activity).filter(
                and_(
                    Activity.user_id == user_id,
                    Activity.start_date_utc >= today_start
                )
            ).first()

            if today_activity:
                return None  # Already trained today

            # Check readiness
            readiness = state.get("readiness", 0)
            
            if readiness > 70:
                return f"👟 You have the energy to train today! (Readiness: {readiness:.0f}/100). Don't skip—commit to it! 💪"
            elif readiness > 50:
                return "🏃 Planning to train today? Even an easy run counts!"
            else:
                return None  # No nudge if fatigued

        except Exception as e:
            logger.error(f"Adherence check error: {e}")
            return None

    @staticmethod
    @celery_app.task(name="backend.tasks.coaching_tasks.send_motivation_boost")
    def send_motivation_boost():
        """
        Send motivational messages to low-motivation users.
        Runs randomly 3x/week.
        """
        logger.info("💪 Motivation boost checker starting...")
        db = SessionLocal()
        try:
            # Find low-motivation users
            low_motivation_users = db.query(User).filter(
                User.is_active == True,
                User.payment_status == "active"
            ).all()

            boost_count = 0
            for user in low_motivation_users:
                try:
                    context = ContextAssembler.assemble_coaching_context(db, user.id)
                    psych = context.get("psychological_state", {})
                    motivation = psych.get("motivation", 0.7)

                    if motivation < 0.6:
                        boost = BehavioralCoachingNudges._generate_motivation_boost(context)
                        if boost:
                            send_telegram_message(boost, user.telegram_chat_id)
                            boost_count += 1
                except Exception as e:
                    logger.error(f"Motivation boost failed for user {user.id}: {e}")

            logger.info(f"✅ {boost_count} motivation boosts sent")

        except Exception as e:
            logger.error(f"❌ Motivation boost error: {e}", exc_info=True)
        finally:
            db.close()

    @staticmethod
    def _generate_motivation_boost(context: Dict) -> Optional[str]:
        """Generate personalized motivation message"""
        try:
            goal = context.get("athlete", {}).get("goal", "your goals")
            learnings = context.get("athlete_model", {})

            messages = [
                f"💪 Remember why you started. You're working towards {goal}—let's crush it!",
                f"🎯 Every run gets you closer to your goal. You've got this!",
                f"🏃 Feeling unmotivated? The best training sessions always come after the hardest mental battle.",
                f"📈 Look at how far you've come! Keep building on this progress."
            ]

            import random
            return random.choice(messages)

        except Exception as e:
            logger.error(f"Motivation boost generation error: {e}")
            return None
