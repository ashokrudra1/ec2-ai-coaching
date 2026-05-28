from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict

from backend.athlete_state.predictive_engine import PredictiveEngine
from backend.recovery.recovery_optimizer import RecoveryOptimizer


@dataclass(frozen=True)
class DigitalTwinProjection:
    readiness_24h: float
    readiness_72h: float
    injury_trajectory_14d: float
    burnout_trajectory_21d: float
    adaptation_potential_7d: float
    glycogen_state: str
    projected_state_at: str


class DigitalTwinEngine:
    """
    Runtime simulation layer for continuously evolving athlete twin state.
    """

    @staticmethod
    def estimate_glycogen_state(load_tss_24h: float, carb_quality_score: float) -> str:
        glycogen_score = max(0.0, min(1.0, 0.65 * carb_quality_score - 0.004 * load_tss_24h + 0.45))
        if glycogen_score >= 0.72:
            return "replenished"
        if glycogen_score >= 0.45:
            return "partial"
        return "depleted"

    @staticmethod
    def simulate(context: Dict) -> DigitalTwinProjection:
        fatigue = context.get("fatigue_metrics", {}) or {}
        physiological = context.get("physiological", {}) or {}
        psychological = context.get("psychological", {}) or {}

        tsb = float(fatigue.get("tsb", 0.0) or 0.0)
        acwr = float(fatigue.get("acwr", 1.0) or 1.0)
        tss_24h = float(fatigue.get("tss_24h", 0.0) or 0.0)
        carb_quality_score = float(physiological.get("carb_quality_score", 0.6) or 0.6)

        recovery_snapshot = RecoveryOptimizer.compute_recovery_state(
            hrv_baseline=float(physiological.get("hrv_baseline", 60.0) or 60.0),
            hrv_today=float(physiological.get("hrv_today", 58.0) or 58.0),
            sleep_hours=float(physiological.get("sleep_hours", 7.0) or 7.0),
            load_tss_24h=tss_24h,
            resting_hr_delta=float(physiological.get("resting_hr_delta", 0.0) or 0.0),
        )

        predictive_context = {
            "fatigue_metrics": {"acwr": acwr, "ctl": fatigue.get("ctl", 0.0), "tsb": tsb},
            "physiological": {
                "structural_decay_rate": float(physiological.get("structural_decay_rate", 0.0) or 0.0),
                "aerobic_drift_velocity": float(physiological.get("aerobic_drift_velocity", 0.0) or 0.0),
            },
            "behavioral": {"compliance_rate": float(context.get("behavioral", {}).get("compliance_rate", 1.0) or 1.0)},
            "psychological": {
                "burnout_risk": float(psychological.get("burnout_risk", 0.1) or 0.1),
                "frustration_index": float(psychological.get("frustration_index", 0.1) or 0.1),
                "adherence_velocity": float(psychological.get("adherence_velocity", 1.0) or 1.0),
            },
        }
        risks = PredictiveEngine.forecast_risk_profiles(predictive_context)

        readiness_24h = max(0.0, min(1.0, recovery_snapshot["readiness_score"] / 100.0))
        readiness_72h = max(0.0, min(1.0, readiness_24h + 0.08 - max(0.0, (acwr - 1.2) * 0.12)))
        adaptation_potential_7d = max(0.0, min(1.0, 0.55 * readiness_72h + 0.45 * max(0.0, min(1.0, (tsb + 15.0) / 25.0))))

        return DigitalTwinProjection(
            readiness_24h=round(readiness_24h, 3),
            readiness_72h=round(readiness_72h, 3),
            injury_trajectory_14d=round(float(risks.get("injury_probability_14d", 0.0) or 0.0), 3),
            burnout_trajectory_21d=round(float(risks.get("burnout_probability_21d", 0.0) or 0.0), 3),
            adaptation_potential_7d=round(adaptation_potential_7d, 3),
            glycogen_state=DigitalTwinEngine.estimate_glycogen_state(tss_24h, carb_quality_score),
            projected_state_at=(datetime.utcnow() + timedelta(hours=72)).isoformat(),
        )
