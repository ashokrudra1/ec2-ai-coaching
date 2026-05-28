from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class LiveSignal:
    avg_hr: float
    hr_threshold: float
    pace_sec_per_km: float
    target_pace_sec_per_km: float
    cardiac_drift: float
    heat_index_c: float


class LiveCoachingInterventionEngine:
    @staticmethod
    def evaluate(signal: LiveSignal) -> List[Dict]:
        interventions: List[Dict] = []
        if signal.cardiac_drift > 7.0:
            interventions.append(
                {
                    "type": "intensity_downgrade",
                    "action": "reduce_target_power_or_pace_by_5_to_8_percent",
                    "reason": "cardiac_drift_above_7_percent",
                }
            )
        if signal.avg_hr > signal.hr_threshold:
            interventions.append(
                {
                    "type": "session_adjustment",
                    "action": "shorten_remaining_session_by_15_percent",
                    "reason": "hr_above_threshold",
                }
            )
        if signal.pace_sec_per_km > signal.target_pace_sec_per_km * 1.08:
            interventions.append(
                {
                    "type": "pace_guardrail",
                    "action": "switch_to_recovery_effort_until_hr_normalizes",
                    "reason": "pace_drift_detected",
                }
            )
        if signal.heat_index_c >= 33.0:
            interventions.append(
                {
                    "type": "heat_safety",
                    "action": "increase_hydration_frequency_and_reduce_intensity",
                    "reason": "heat_stress_risk",
                }
            )
        return interventions
