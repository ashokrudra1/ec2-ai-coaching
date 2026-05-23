# backend/athlete_state/predictive_engine.py
import math
import logging
from backend.models import User, Activity

logger = logging.getLogger(__name__)

class PredictiveEngine:
    """
    Predictive Injury, Burnout, and Plateau Forecasting Engine.
    Processes multi-factor metrics to flag issues before they manifest physically.
    """

    @staticmethod
    def sigmoid(x: float) -> float:
        """Standard sigmoid activation function."""
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def forecast_risk_profiles(context: dict) -> dict:
        """
        Computes training risks dynamically using standard predictive equations.
        Outputs: 14-day injury risk, 21-day burnout risk, and aerobic plateau probability.
        """
        try:
            # 1. 14-Day Injury Probability (Weighted Logistic Model)
            acwr = context.get("fatigue_metrics", {}).get("acwr", 1.0)
            decay = context.get("physiological", {}).get("structural_decay_rate", 0.0)
            compliance = context.get("behavioral", {}).get("compliance_rate", 1.0)

            # High ACWR spikes, cadence degradation, and compliance errors scale injury risk
            injury_logit = (
                (3.5 * (acwr - 1.25)) + 
                (22.0 * decay) + 
                (0.5 * (1.0 - compliance)) - 
                1.8
            )
            injury_prob = round(PredictiveEngine.sigmoid(injury_logit), 2)

            # 2. 21-Day Burnout Probability (Weighted Logistic Model)
            burnout_risk_indicator = context.get("psychological", {}).get("burnout_risk", 0.05)
            frustration = context.get("psychological", {}).get("frustration_index", 0.1)
            adherence_velocity = context.get("psychological", {}).get("adherence_velocity", 1.0)

            burnout_logit = (
                (2.8 * burnout_risk_indicator) + 
                (1.5 * frustration) - 
                (2.0 * adherence_velocity) + 
                0.2
            )
            burnout_prob = round(PredictiveEngine.sigmoid(burnout_logit), 2)

            # 3. Aerobic Plateau Risk
            # Identified when high chronic load (CTL) is accompanied by rising aerobic drift (drift velocity)
            ctl = context.get("fatigue_metrics", {}).get("ctl", 20.0)
            drift_velocity = context.get("physiological", {}).get("aerobic_drift_velocity", 0.0)

            plateau_prob = 0.10
            if ctl > 40.0 and drift_velocity > 0.03:
                plateau_prob = round(min(0.95, 0.15 + (ctl / 100.0) * (drift_velocity * 10.0)), 2)

            return {
                "injury_probability_14d": injury_prob,
                "burnout_probability_21d": burnout_prob,
                "plateau_risk": plateau_prob
            }

        except Exception as e:
            logger.error(f"❌ PredictiveEngine forecasting failed: {str(e)}")
            return {"injury_probability_14d": 0.10, "burnout_probability_21d": 0.05, "plateau_risk": 0.15}
