from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class RecoveryState:
    hrv_suppression: float
    autonomic_stress: float
    sleep_debt_hours: float
    parasympathetic_rebound: float
    glycogen_restoration: float
    muscle_damage_proxy: float
    readiness_score: float


class RecoveryOptimizer:
    @staticmethod
    def compute_recovery_state(
        *,
        hrv_baseline: float,
        hrv_today: float,
        sleep_hours: float,
        load_tss_24h: float,
        resting_hr_delta: float,
    ) -> Dict:
        hrv_suppression = max(0.0, min(1.0, (hrv_baseline - hrv_today) / max(hrv_baseline, 1.0)))
        sleep_debt_hours = max(0.0, 8.0 - max(0.0, sleep_hours))
        autonomic_stress = max(
            0.0,
            min(1.0, 0.55 * hrv_suppression + 0.25 * min(1.0, sleep_debt_hours / 3.0) + 0.20 * min(1.0, resting_hr_delta / 8.0)),
        )
        parasympathetic_rebound = max(0.0, min(1.0, 1.0 - autonomic_stress))
        glycogen_restoration = max(0.0, min(1.0, 1.0 - min(1.0, load_tss_24h / 220.0) + 0.2 * parasympathetic_rebound))
        muscle_damage_proxy = max(0.0, min(1.0, 0.65 * min(1.0, load_tss_24h / 180.0) + 0.35 * autonomic_stress))
        readiness_score = max(
            0.0,
            min(100.0, 100.0 - (55.0 * autonomic_stress + 20.0 * min(1.0, sleep_debt_hours / 4.0) + 25.0 * muscle_damage_proxy)),
        )
        return RecoveryState(
            hrv_suppression=round(hrv_suppression, 3),
            autonomic_stress=round(autonomic_stress, 3),
            sleep_debt_hours=round(sleep_debt_hours, 2),
            parasympathetic_rebound=round(parasympathetic_rebound, 3),
            glycogen_restoration=round(glycogen_restoration, 3),
            muscle_damage_proxy=round(muscle_damage_proxy, 3),
            readiness_score=round(readiness_score, 1),
        ).__dict__

    @staticmethod
    def daily_recovery_protocol(recovery_state: Dict) -> List[str]:
        protocol: List[str] = []
        if recovery_state.get("glycogen_restoration", 1.0) < 0.5:
            protocol.append("carb_loading_1_to_1_2g_per_kg_within_2h")
            protocol.append("hydration_750ml_with_electrolytes")
        if recovery_state.get("sleep_debt_hours", 0.0) > 1.5:
            protocol.append("sleep_extension_plus_60_to_90min")
        if recovery_state.get("autonomic_stress", 0.0) > 0.55:
            protocol.append("mobility_20min_and_breathing_drill")
            protocol.append("cold_exposure_3_to_5min_optional")
        if recovery_state.get("muscle_damage_proxy", 0.0) > 0.5:
            protocol.append("compression_or_light_flush_cycle")
            protocol.append("sauna_10_to_15min_if_tolerated")
        if not protocol:
            protocol.append("maintenance_recovery_walk_and_hydration")
        return protocol
