# backend/orchestration/athlete_state_builder.py
import logging
from sqlalchemy import desc
from backend.models import User, Activity, AthleteInsight
from backend.athlete_state.digital_twin_engine import DigitalTwinEngine
from backend.athlete_state.fatigue_engine import FatigueEngine
from backend.athlete_state.recovery_engine import RecoveryEngine
from backend.athlete_state.injury_risk_engine import InjuryRiskEngine
from backend.athlete_state.physiology_engine import PhysiologyEngine
from backend.recovery.recovery_optimizer import RecoveryOptimizer

logger = logging.getLogger(__name__)

class AthleteStateBuilder:

    @staticmethod
    def build(db, user_id):
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User with ID {user_id} not found.")

        fatigue = FatigueEngine.calculate(db, user_id)
        zones = PhysiologyEngine.calculate_hr_zones(user)

        recent_activities = (
            db.query(Activity)
            .filter_by(user_id=user_id)
            .order_by(Activity.start_date_utc.desc())
            .limit(10)
            .all()
        )

        # 🔴 HIGH SPEC HARDENING: INSTANT BLANK BASELINE RETURN IF ACCOUNT HAS NO ACTIVITIES
        if not recent_activities:
            return {
                "user_id": user.id,
                "name": user.name,
                "goal": user.target_goal or "Sub-4 Marathon",
                "coaching_state": user.coaching_state or "Active Base",
                "fatigue_metrics": fatigue,
                "recovery_score": 100.0,
                "hr_zones": zones,
                "glycogen_depleted_g": 0.0,
                "physiological": {
                    "threshold_pace": user.physiological_twin.get("threshold_pace", 300) if user.physiological_twin else 300,
                    "threshold_hr": user.physiological_twin.get("threshold_hr", 165) if user.physiological_twin else 165,
                    "vo2max_estimate": user.physiological_twin.get("vo2max_estimate", 48.0) if user.physiological_twin else 48.0,
                    "aerobic_drift_velocity": 0.0,
                    "structural_decay_rate": 0.0
                },
                "behavioral": {
                    "compliance_rate": 1.0,
                    "skips_easy_runs": False,
                    "runs_easy_too_hard": False,
                    "heat_sensitivity_index": 0.5
                },
                "psychological": {
                    "confidence": 0.8,
                    "anxiety": 0.2,
                    "motivation": 0.8,
                    "burnout_risk": 0.05,
                    "adherence_velocity": 1.0,
                    "frustration_index": 0.0
                },
                "predictive_risk": {
                    "injury_probability_14d": 0.10,
                    "burnout_probability_21d": 0.05,
                    "plateau_risk": 0.10
                },
                "cardiovascular_trends": {
                    "latest_cardiac_decoupling": 0.0,
                    "latest_stride_degradation": 0.0,
                    "elevated_cardiac_cost_detected": False,
                    "stride_collapse_detected": False
                }
            }

        current_decoupling = 0.0
        current_degradation = 0.0
        current_glycogen = 0.0

        decoupling_trend = []
        degradation_trend = []

        for act in recent_activities:
            if act.cardiac_decoupling is not None:
                decoupling_trend.append(act.cardiac_decoupling)
            if act.cadence_degradation is not None:
                degradation_trend.append(act.cadence_degradation)

        latest = recent_activities[0]
        current_decoupling = latest.cardiac_decoupling or 0.0
        current_degradation = latest.cadence_degradation or 0.0
        current_glycogen = latest.glycogen_depleted_g or 0.0

        aerobic_drift_velocity = 0.0
        if len(decoupling_trend) >= 3:
            aerobic_drift_velocity = round(decoupling_trend[0] - sum(decoupling_trend) / len(decoupling_trend), 3)

        structural_decay_rate = 0.0
        if len(degradation_trend) >= 3:
            structural_decay_rate = round(degradation_trend[0] - sum(degradation_trend) / len(degradation_trend), 3)

        user_phys = user.physiological_twin or {}
        physiological_twin = {
            "threshold_pace": user_phys.get("threshold_pace", 300),
            "threshold_hr": user_phys.get("threshold_hr", 165),
            "vo2max_estimate": user_phys.get("vo2max_estimate", 48.0),
            "aerobic_drift_velocity": aerobic_drift_velocity,
            "structural_decay_rate": structural_decay_rate
        }

        runs_easy_too_hard = False
        compliance_check = recent_activities  # Re-use loaded items
        easy_runs = [a for a in compliance_check if "Easy" in (a.name or "")]
        if easy_runs:
            hard_easy_runs = [e for e in easy_runs if (e.avg_heart_rate or 0) > (user.rest_hr + (user.max_hr - user.rest_hr) * 0.75)]
            if len(hard_easy_runs) / len(easy_runs) > 0.35:
                runs_easy_too_hard = True

        user_beh = user.behavioral_twin or {}
        behavioral_twin = {
            "compliance_rate": round(user_beh.get("compliance_rate", 0.95), 2),
            "skips_easy_runs": user_beh.get("skips_easy_runs", False),
            "runs_easy_too_hard": runs_easy_too_hard,
            "heat_sensitivity_index": user_beh.get("heat_sensitivity_index", 0.5)
        }

        burnout_risk = 0.05
        frustration_index = 0.1
        adherence_velocity = 1.0

        if len(compliance_check) >= 5:
            missed_runs = [c for c in compliance_check[:5] if (c.moving_time_min or 0) == 0]
            if len(missed_runs) >= 2:
                burnout_risk = 0.72
                adherence_velocity = 0.4
                frustration_index = 0.65

        user_psych = user.psychological_twin or {}
        psychological_twin = {
            "confidence": user_psych.get("confidence", 0.8),
            "anxiety": user_psych.get("anxiety", 0.2),
            "motivation": user_psych.get("motivation", 0.8),
            "burnout_risk": burnout_risk,
            "adherence_velocity": adherence_velocity,
            "frustration_index": frustration_index
        }

        cardiac_load_penalty = min(30.0, current_decoupling * 100.0)
        durability_penalty = min(30.0, current_degradation * 100.0)
        glycogen_depletion_cost = min(20.0, (current_glycogen / 350.0) * 20.0)

        latest_temp = recent_activities[0].temperature_c if recent_activities else 20.0
        heat_cost_penalty = max(0.0, (latest_temp - 25.0) * 1.5) if latest_temp else 0.0

        raw_recovery = 100.0 - (cardiac_load_penalty + durability_penalty + glycogen_depletion_cost + heat_cost_penalty)
        recovery_score = float(round(max(30.0, min(100.0, raw_recovery)), 1))

        acwr = fatigue.get("acwr", 1.0)
        injury_probability_14d = 0.10
        if acwr > 1.5:
            injury_probability_14d = 0.68
        elif acwr > 1.2 or structural_decay_rate > 0.03:
            injury_probability_14d = 0.42

        burnout_probability_21d = 0.05
        if burnout_risk > 0.50 or adherence_velocity < 0.60:
            burnout_probability_21d = 0.67

        plateau_risk = 0.15
        if aerobic_drift_velocity > 0.04 and user.ctl > 40.0:
            plateau_risk = 0.51

        predictive_risk = {
            "injury_probability_14d": injury_probability_14d,
            "burnout_probability_21d": burnout_probability_21d,
            "plateau_risk": plateau_risk
        }

        twin_projection = DigitalTwinEngine.simulate(
            {
                "fatigue_metrics": fatigue,
                "physiological": physiological_twin,
                "behavioral": behavioral_twin,
                "psychological": psychological_twin,
            }
        )
        recovery_state = RecoveryOptimizer.compute_recovery_state(
            hrv_baseline=float(physiological_twin.get("hrv_baseline", 60.0) or 60.0),
            hrv_today=float(physiological_twin.get("hrv_today", 58.0) or 58.0),
            sleep_hours=float(physiological_twin.get("sleep_hours", 7.0) or 7.0),
            load_tss_24h=float(fatigue.get("acute_load", 0.0) or 0.0),
            resting_hr_delta=float(physiological_twin.get("resting_hr_delta", 0.0) or 0.0),
        )

        return {
            "user_id": user.id,
            "name": user.name,
            "goal": user.target_goal or "Sub-4 Marathon",
            "coaching_state": user.coaching_state or "Active Base",
            "fatigue_metrics": fatigue,
            "recovery_score": recovery_score,
            "hr_zones": zones,
            "glycogen_depleted_g": current_glycogen,
            "physiological": physiological_twin,
            "behavioral": behavioral_twin,
            "psychological": psychological_twin,
            "predictive_risk": predictive_risk,
            "digital_twin_projection": twin_projection.__dict__,
            "recovery_state": recovery_state,
            "daily_recovery_protocol": RecoveryOptimizer.daily_recovery_protocol(recovery_state),
            "cardiovascular_trends": {
                "latest_cardiac_decoupling": current_decoupling,
                "latest_stride_degradation": current_degradation,
                "elevated_cardiac_cost_detected": current_decoupling > 0.05,
                "stride_collapse_detected": current_degradation > 0.04
            }
        }
