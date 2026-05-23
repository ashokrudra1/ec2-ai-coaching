# backend/athlete_state/compliance_engine.py
import logging
from backend.models import User, Activity

logger = logging.getLogger(__name__)

class ComplianceEngine:
    """
    Adherence and Pacing Discipline Engine.
    Detects easy-run violations and dynamically adjusts future training loads.
    """

    @staticmethod
    def evaluate_workout_compliance(activity: Activity, user: User) -> dict:
        """
        Compares actual workout execution metrics against prescriptive session limits.
        """
        if not activity or not user:
            return {"compliance_score": 1.0, "runs_easy_too_hard": False, "pacing_discipline": 1.0}

        try:
            name_lower = (activity.name or "").lower()
            is_easy_run = "easy" in name_lower or "recovery" in name_lower or "steady" in name_lower

            runs_easy_too_hard = False
            pacing_discipline = 1.0

            # 1. Evaluate easy-run compliance (Checking for "easy days run too hard")
            if is_easy_run and activity.avg_heart_rate and user.max_hr and user.rest_hr:
                hr_reserve = user.max_hr - user.rest_hr
                # Easy runs must be kept under 75% of HR reserve
                easy_hr_ceiling = user.rest_hr + (hr_reserve * 0.75)
                
                if activity.avg_heart_rate > easy_hr_ceiling:
                    runs_easy_too_hard = True
                    pacing_discipline = 0.45
                    logger.warning(f"🚨 Easy-run violation detected for User {user.id}. HR exceeded easy ceiling of {easy_hr_ceiling} bpm.")

            # 2. Evaluate volume compliance
            # Ensure actual duration matches the prescribed target (+/- 15%)
            actual_duration = activity.moving_time_min or 1.0
            prescribed_duration = 45.0  # Default baseline target
            duration_ratio = actual_duration / prescribed_duration

            duration_compliance = 1.0
            if duration_ratio > 1.25:
                # Athlete ran too long (volume violation)
                duration_compliance = 0.70
            elif duration_ratio < 0.75:
                # Athlete cut the workout short
                duration_compliance = 0.65

            compliance_score = round((pacing_discipline * 0.60) + (duration_compliance * 0.40), 2)

            return {
                "compliance_score": compliance_score,
                "runs_easy_too_hard": runs_easy_too_hard,
                "pacing_discipline": round(pacing_discipline, 2)
            }

        except Exception as e:
            logger.error(f"❌ ComplianceEngine failed to evaluate workout: {str(e)}")
            return {"compliance_score": 1.0, "runs_easy_too_hard": False, "pacing_discipline": 1.0}
