from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import Activity, SafetyAlert, User
from backend.notifications import send_telegram_message
from backend.sports_science.compliance import WorkoutComplianceEngine
from backend.sports_science.state_space import StateSpaceDecayModel
from backend.sports_science.twin_service import PhysiologyTwinService
from backend.events.event_bus import event_bus
from backend.events import domain_events


class AthleteMonitoringService:
    TSB_CRITICAL = -20.0

    @classmethod
    def process_activity(cls, db: Session, activity: Activity, user: Optional[User] = None) -> None:
        user = user or db.query(User).filter_by(id=activity.user_id).first()
        if not user:
            return

        compliance = WorkoutComplianceEngine.evaluate_activity(activity, user)
        activity.compliance_score = compliance.overall_score
        activity.pace_compliance_score = compliance.pace_score
        activity.hr_compliance_score = compliance.hr_score
        activity.compliance_breakdown = compliance.breakdown
        activity.cardiac_decoupling = compliance.cardiac_decoupling

        if not activity.training_stress_score_tss:
            from backend.analytics import calculate_activity_tss
            activity.training_stress_score_tss = calculate_activity_tss(activity, user)

        event_time = activity.start_date_utc or datetime.utcnow()
        elapsed_days = cls._elapsed_days(user.fitness_state_updated_at, activity.start_date_utc)
        state = PhysiologyTwinService.advance_training_load_state(
            user=user,
            stress=activity.training_stress_score_tss or 0.0,
            elapsed_days=elapsed_days,
            event_time=event_time,
        )
        PhysiologyTwinService.update_twins_from_activity(
            db,
            user=user,
            activity=activity,
            compliance=compliance,
            training_load_state=state,
        )

        cls.ensure_fatigue_alert(db, user, state.tsb)
        biomech = (user.physiological_twin or {}).get("biomechanical_risk_proxy", {})
        if biomech.get("risk_level") == "high":
            cls.ensure_biomechanical_alert(db, user, biomech)

        try:
            event_bus.publish(
                domain_events.workout_ingested(
                    event_id=f"workout:{user.id}:{activity.id or activity.strava_id or 'na'}",
                    user_id=user.id,
                    activity_id=activity.id or 0,
                    payload={"tsb": state.tsb, "ctl": state.ctl, "atl": state.atl, "acwr": state.acwr},
                )
            )
            event_bus.publish(
                domain_events.athlete_state_updated(
                    event_id=f"athlete_state:{user.id}:{activity.id or activity.strava_id or 'na'}",
                    user_id=user.id,
                    payload={"tsb": state.tsb, "ctl": state.ctl, "atl": state.atl, "acwr": state.acwr},
                )
            )
            event_bus.publish(
                domain_events.readiness_updated(
                    event_id=f"readiness:{user.id}:{activity.id or activity.strava_id or 'na'}",
                    user_id=user.id,
                    payload={
                        "tsb": state.tsb,
                        "injury_risk_score": state.injury_risk_score,
                        "fatigue_level": state.fatigue_level,
                    },
                )
            )
        except Exception:
            # Never fail activity processing for event emission.
            pass
        db.add(activity)
        db.add(user)

    @classmethod
    def refresh_user_state(cls, db: Session, user: User) -> None:
        state = PhysiologyTwinService.decay_training_load_to_now(user=user)
        cls.ensure_fatigue_alert(db, user, state.tsb)
        db.add(user)

    @classmethod
    def ensure_fatigue_alert(cls, db: Session, user: User, tsb: float) -> Optional[SafetyAlert]:
        if tsb >= cls.TSB_CRITICAL:
            return None

        existing = db.query(SafetyAlert).filter(
            SafetyAlert.user_id == user.id,
            SafetyAlert.alert_type == "fatigue_guardrail",
            SafetyAlert.is_resolved == False,
        ).first()
        if existing:
            return existing

        alert = SafetyAlert(
            user_id=user.id,
            alert_type="fatigue_guardrail",
            severity="critical",
            message=f"TSB is {tsb:.1f}. Hard training is blocked until recovery improves.",
            source_metric="tsb",
            source_value=tsb,
        )
        db.add(alert)
        if user.telegram_chat_id:
            send_telegram_message(
                "🚨 *Fatigue Guardrail Active:* Your form score has dropped into a high-risk zone. "
                "Veda is switching you to injury-prevention coaching and will block hard training until recovery improves.",
                user.telegram_chat_id,
            )
        return alert

    @classmethod
    def ensure_biomechanical_alert(cls, db: Session, user: User, biomech: dict) -> Optional[SafetyAlert]:
        existing = db.query(SafetyAlert).filter(
            SafetyAlert.user_id == user.id,
            SafetyAlert.alert_type == "biomechanical_risk",
            SafetyAlert.is_resolved == False,
        ).first()
        if existing:
            return existing

        alert = SafetyAlert(
            user_id=user.id,
            alert_type="biomechanical_risk",
            severity="warning",
            message=(
                "Biomechanical risk proxy is elevated. Reduce pace intensity and prioritize stride stability, "
                "mobility, and recovery."
            ),
            source_metric="biomechanical_risk_proxy",
            source_value=1.0,
        )
        db.add(alert)
        return alert

    @staticmethod
    def _elapsed_days(previous: Optional[datetime], current: Optional[datetime]) -> float:
        if not previous or not current:
            return 1.0
        return max(0.0, (current - previous).total_seconds() / 86400.0)

    @staticmethod
    def _rolling_compliance(db: Session, user_id: int, latest_score: float) -> float:
        recent = db.query(Activity.compliance_score).filter(
            Activity.user_id == user_id,
            Activity.compliance_score.isnot(None),
        ).order_by(Activity.start_date_utc.desc()).limit(9).all()
        scores = [row[0] for row in recent if row[0] is not None]
        scores.insert(0, latest_score)
        return round(sum(scores) / len(scores), 3) if scores else round(latest_score, 3)
