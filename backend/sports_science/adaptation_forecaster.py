from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class AdaptationForecast:
    adaptation_probability_7d: float
    fatigue_risk_7d: float
    injury_probability_14d: float
    burnout_probability_21d: float
    readiness_next_72h: float


class AdaptationForecaster:
    """
    Deterministic adaptation forecaster based on training load, recovery proxy,
    and aerobic stress signals.
    """

    @staticmethod
    def forecast(*, tsb: float, acwr: float, recovery_index: float, cardiac_decoupling: float) -> AdaptationForecast:
        recovery_norm = max(0.0, min(1.0, (recovery_index or 0.0) / 100.0))
        freshness_norm = max(0.0, min(1.0, (tsb + 20.0) / 40.0))
        acwr_penalty = max(0.0, min(1.0, (acwr - 1.0) / 0.8))
        decoupling_penalty = max(0.0, min(1.0, (cardiac_decoupling or 0.0) / 0.12))

        adaptation_probability_7d = max(
            0.0,
            min(1.0, 0.55 * recovery_norm + 0.45 * freshness_norm - 0.20 * acwr_penalty),
        )
        fatigue_risk_7d = max(
            0.0,
            min(1.0, 0.45 * (1.0 - freshness_norm) + 0.35 * acwr_penalty + 0.20 * decoupling_penalty),
        )
        injury_probability_14d = max(
            0.0,
            min(1.0, 0.50 * acwr_penalty + 0.35 * decoupling_penalty + 0.15 * (1.0 - recovery_norm)),
        )
        burnout_probability_21d = max(
            0.0,
            min(1.0, 0.40 * fatigue_risk_7d + 0.30 * (1.0 - recovery_norm) + 0.30 * (1.0 - adaptation_probability_7d)),
        )
        readiness_next_72h = max(0.0, min(1.0, 0.60 * recovery_norm + 0.40 * freshness_norm))

        return AdaptationForecast(
            adaptation_probability_7d=round(adaptation_probability_7d, 3),
            fatigue_risk_7d=round(fatigue_risk_7d, 3),
            injury_probability_14d=round(injury_probability_14d, 3),
            burnout_probability_21d=round(burnout_probability_21d, 3),
            readiness_next_72h=round(readiness_next_72h, 3),
        )

    @staticmethod
    def classify_injury_risk(probability_14d: float) -> str:
        if probability_14d >= 0.65:
            return "high"
        if probability_14d >= 0.40:
            return "moderate"
        return "low"

    @staticmethod
    def summarize_for_trace(forecast: AdaptationForecast) -> Dict[str, float]:
        return {
            "adaptation_probability_7d": forecast.adaptation_probability_7d,
            "fatigue_risk_7d": forecast.fatigue_risk_7d,
            "injury_probability_14d": forecast.injury_probability_14d,
            "burnout_probability_21d": forecast.burnout_probability_21d,
            "readiness_next_72h": forecast.readiness_next_72h,
        }
