from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.models import Activity, User
from backend.orchestration.metrics_engine import TrainingMetricsEngine
from backend.sports_science.adaptation_forecaster import AdaptationForecaster
from backend.sports_science.state_space import StateSpaceDecayModel, TrainingLoadState


class PhysiologyTwinService:
    """
    Canonical service for maintaining the athlete's longitudinal physiological twin.

    Design goals:
    - Deterministic, testable outputs (no LLM dependency).
    - Versioned schema stored in `User.physiological_twin` and `User.behavioral_twin`.
    - Small, composable pure functions for recovery/adaptation/risk proxies.
    """

    TWIN_SCHEMA_VERSION = 1

    @classmethod
    def advance_training_load_state(
        cls,
        *,
        user: User,
        stress: float,
        elapsed_days: float,
        event_time: Optional[datetime],
    ) -> TrainingLoadState:
        state = StateSpaceDecayModel.advance_state(
            ctl=user.ctl or 0.0,
            atl=user.atl or 0.0,
            stress=stress or 0.0,
            elapsed_days=elapsed_days,
            ctl_tau_days=user.ctl_time_constant_days or StateSpaceDecayModel.CTL_TAU_DAYS,
            atl_tau_days=user.atl_time_constant_days or StateSpaceDecayModel.ATL_TAU_DAYS,
        )
        user.ctl = state.ctl
        user.atl = state.atl
        user.tsb = state.tsb
        user.fitness_state_updated_at = event_time
        user.last_training_stress_date = event_time
        return state

    @classmethod
    def decay_training_load_to_now(cls, *, user: User) -> TrainingLoadState:
        state = StateSpaceDecayModel.decay_to_date(
            ctl=user.ctl or 0.0,
            atl=user.atl or 0.0,
            last_updated_at=user.fitness_state_updated_at,
            ctl_tau_days=user.ctl_time_constant_days or StateSpaceDecayModel.CTL_TAU_DAYS,
            atl_tau_days=user.atl_time_constant_days or StateSpaceDecayModel.ATL_TAU_DAYS,
        )
        user.ctl = state.ctl
        user.atl = state.atl
        user.tsb = state.tsb
        user.fitness_state_updated_at = datetime.utcnow()
        return state

    @classmethod
    def update_twins_from_activity(
        cls,
        db: Session,
        *,
        user: User,
        activity: Activity,
        compliance: Any,
        training_load_state: TrainingLoadState,
    ) -> None:
        # Physiological twin (versioned schema)
        physiological = dict(user.physiological_twin or {})
        physiological.setdefault("_schema_version", cls.TWIN_SCHEMA_VERSION)

        physiological["aerobic_drift_velocity"] = getattr(compliance, "cardiac_decoupling", 0.0) or 0.0
        physiological["load_state"] = asdict(training_load_state)
        physiological["recovery_index"] = cls.compute_recovery_index(
            tsb=training_load_state.tsb,
            cardiac_decoupling=getattr(compliance, "cardiac_decoupling", 0.0) or 0.0,
            injury_risk_score=training_load_state.injury_risk_score,
        )
        physiological["adaptation_window_72h"] = cls.compute_adaptation_window_72h(
            tsb=training_load_state.tsb,
            recovery_index=physiological["recovery_index"],
        )
        physiological["biomechanical_risk_proxy"] = cls.compute_biomechanical_risk_proxy(
            cardiac_decoupling=getattr(compliance, "cardiac_decoupling", 0.0) or 0.0,
            avg_cadence=activity.avg_cadence,
        )
        forecast = AdaptationForecaster.forecast(
            tsb=training_load_state.tsb,
            acwr=training_load_state.acwr,
            recovery_index=physiological["recovery_index"],
            cardiac_decoupling=getattr(compliance, "cardiac_decoupling", 0.0) or 0.0,
        )
        physiological["adaptation_forecast"] = AdaptationForecaster.summarize_for_trace(forecast)
        physiological["injury_risk_classification"] = AdaptationForecaster.classify_injury_risk(
            forecast.injury_probability_14d
        )
        # Conservative race projection signal derived from current 5K pace proxy.
        pace_proxy = float(activity.moving_time_min * 60.0 / max(activity.distance_km or 0.001, 0.001))
        physiological["race_projection_10k_sec_per_km"] = cls.estimate_race_performance(
            pace_5k_sec_per_km=pace_proxy,
            vo2_max_percent=1.0 + max(-0.08, min(0.12, (physiological["adaptation_window_72h"] - 0.5) * 0.2)),
            ctl_strain_factor=1.0 - max(0.0, min(0.15, abs(training_load_state.tsb) / 100.0)),
            target_distance_km=10.0,
        )

        user.physiological_twin = physiological

        # Behavioral twin
        behavioral = dict(user.behavioral_twin or {})
        behavioral.setdefault("_schema_version", 1)
        behavioral["compliance_rate"] = cls._rolling_compliance(
            db,
            user.id,
            latest_score=getattr(compliance, "overall_score", None),
        )
        user.behavioral_twin = behavioral

    @staticmethod
    def compute_recovery_index(*, tsb: float, cardiac_decoupling: float, injury_risk_score: float) -> float:
        """
        Deterministic heuristic 0–100 recovery score proxy derived from load + aerobic drift.
        """
        # Load penalty: critical negative TSB is heavy penalty.
        tsb_penalty = 0.0
        if tsb < 0:
            tsb_penalty = min(55.0, abs(tsb) * 2.2)

        drift_penalty = min(25.0, max(0.0, cardiac_decoupling) * 250.0)
        risk_penalty = min(25.0, max(0.0, injury_risk_score) * 30.0)

        raw = 100.0 - (tsb_penalty + drift_penalty + risk_penalty)
        return float(round(max(0.0, min(100.0, raw)), 1))

    @staticmethod
    def compute_adaptation_window_72h(*, tsb: float, recovery_index: float) -> float:
        """
        Probability-like 0–1 score for whether a hard session is likely to yield positive adaptation
        in the next ~72 hours, based on freshness and recovery status.
        """
        # Freshness: favour slightly positive TSB, penalize very negative.
        freshness = max(0.0, min(1.0, (tsb + 15.0) / 30.0))
        recovery = max(0.0, min(1.0, (recovery_index or 0.0) / 100.0))
        return round(0.65 * recovery + 0.35 * freshness, 3)

    @staticmethod
    def compute_biomechanical_risk_proxy(*, cardiac_decoupling: float, avg_cadence: Optional[float]) -> Dict[str, Any]:
        """
        Phase-1 approximation (no new sensors): returns categorical risk based on drift and cadence.
        """
        cadence = avg_cadence or 0.0
        risk_level = "low"
        dominant_factor = "none"

        if cardiac_decoupling > 0.08:
            risk_level = "high"
            dominant_factor = "aerobic_fatigue_proxy"
        elif cardiac_decoupling > 0.05:
            risk_level = "moderate"
            dominant_factor = "aerobic_fatigue_proxy"

        # Very low cadence can correlate with overstriding / fatigue in some athletes.
        if cadence and cadence < 155:
            if risk_level == "low":
                risk_level = "moderate"
                dominant_factor = "low_cadence_proxy"

        return {
            "risk_level": risk_level,
            "dominant_factor": dominant_factor,
            "cardiac_decoupling": round(float(cardiac_decoupling or 0.0), 4),
            "avg_cadence": round(float(cadence), 1) if cadence else None,
        }

    @staticmethod
    def estimate_race_performance(*, pace_5k_sec_per_km: float, vo2_max_percent: float, ctl_strain_factor: float, target_distance_km: float) -> float:
        return TrainingMetricsEngine.predict_race_time(
            current_pace_5k_sec=pace_5k_sec_per_km,
            vo2_max_percent=vo2_max_percent,
            ctl_strain_factor=ctl_strain_factor,
            target_distance_km=target_distance_km,
        )

    @staticmethod
    def _rolling_compliance(db: Session, user_id: int, latest_score: Optional[float]) -> float:
        # Defer import to avoid cycles.
        from backend.models import Activity

        recent = (
            db.query(Activity.compliance_score)
            .filter(Activity.user_id == user_id, Activity.compliance_score.isnot(None))
            .order_by(Activity.start_date_utc.desc())
            .limit(9)
            .all()
        )
        scores = [row[0] for row in recent if row[0] is not None]
        if latest_score is not None:
            scores.insert(0, latest_score)
        if not scores:
            return 1.0
        return round(sum(scores) / len(scores), 3)

