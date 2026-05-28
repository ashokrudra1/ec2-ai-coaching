from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from backend.models import User


@dataclass(frozen=True)
class ProactiveEngagementPlan:
    should_send: bool
    reason: str
    message: str
    urgency: str  # low | medium | high


class AutonomousPlanner:
    """
    Deterministic proactive engagement planner.
    """

    @staticmethod
    def build_checkin_plan(user: User) -> ProactiveEngagementPlan:
        tsb = float(user.tsb or 0.0)
        twin = user.physiological_twin or {}
        adaptation = (twin.get("adaptation_forecast") or {})
        readiness = float(adaptation.get("readiness_next_72h", 0.5) or 0.5)
        injury_p = float(adaptation.get("injury_probability_14d", 0.0) or 0.0)

        if injury_p >= 0.65:
            return ProactiveEngagementPlan(
                should_send=True,
                urgency="high",
                reason="injury_risk_high",
                message=(
                    "Your next 14-day injury risk is elevated. Keep the next session easy, "
                    "prioritize sleep and hydration, and avoid high-intensity intervals today."
                ),
            )

        if tsb < -10.0 or readiness < 0.45:
            return ProactiveEngagementPlan(
                should_send=True,
                urgency="medium",
                reason="recovery_focus",
                message=(
                    "Recovery signal is trending low. Today should be a low-intensity session "
                    "or active recovery to protect adaptation quality."
                ),
            )

        if readiness > 0.70 and -5.0 <= tsb <= 8.0:
            return ProactiveEngagementPlan(
                should_send=True,
                urgency="low",
                reason="quality_window",
                message=(
                    "You are in a strong adaptation window. If schedule permits, this is a good "
                    "time for a structured quality workout with controlled intensity."
                ),
            )

        return ProactiveEngagementPlan(
            should_send=False,
            urgency="low",
            reason="no_proactive_action",
            message="",
        )

    @staticmethod
    def intervention_hint_from_activity(activity_payload: Dict, tsb: float) -> Optional[str]:
        avg_hr = float(activity_payload.get("average_heartrate") or 0.0)
        distance_m = float(activity_payload.get("distance") or 0.0)
        moving_time_s = float(activity_payload.get("moving_time") or 0.0)
        pace_sec_per_km = (moving_time_s / max(distance_m / 1000.0, 0.001)) if moving_time_s and distance_m else 0.0

        if tsb < -15.0 and avg_hr > 0:
            return "Live safeguard: fatigue is high today. Cap effort and keep heart rate in easy zone."
        if avg_hr > 182.0:
            return "Live safeguard: heart rate is unusually high. Slow down and prioritize controlled breathing."
        if pace_sec_per_km > 420 and moving_time_s > 1800:
            return "Live cue: pace drift detected. Shorten this session to preserve recovery quality."
        return None
