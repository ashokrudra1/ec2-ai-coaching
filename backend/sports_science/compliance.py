from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ComplianceResult:
    overall_score: float
    pace_score: Optional[float]
    hr_score: Optional[float]
    duration_score: Optional[float]
    distance_score: Optional[float]
    cardiac_decoupling: float
    breakdown: Dict[str, Any]


class WorkoutComplianceEngine:
    @classmethod
    def evaluate_activity(cls, activity: Any, user: Any = None) -> ComplianceResult:
        prescribed = activity.prescribed_workout or {}
        actual_pace = cls._pace_seconds_per_km(activity.distance_km, activity.moving_time_min)
        actual_hr = activity.avg_heart_rate
        actual_duration = activity.moving_time_min
        actual_distance = activity.distance_km

        pace_score = cls._target_score(actual_pace, prescribed.get("target_pace_sec_per_km"), prescribed.get("pace_tolerance_pct", 0.08), lower_is_better=True)
        hr_score = cls._range_score(actual_hr, prescribed.get("target_hr_min"), prescribed.get("target_hr_max"))
        duration_score = cls._target_score(actual_duration, prescribed.get("target_duration_min"), prescribed.get("duration_tolerance_pct", 0.10))
        distance_score = cls._target_score(actual_distance, prescribed.get("target_distance_km"), prescribed.get("distance_tolerance_pct", 0.10))
        cardiac_decoupling = cls.compute_cardiac_decoupling(activity.splits or [])

        weighted_scores = []
        for score, weight in ((pace_score, 0.30), (hr_score, 0.35), (duration_score, 0.20), (distance_score, 0.15)):
            if score is not None:
                weighted_scores.append((score, weight))

        if weighted_scores:
            total_weight = sum(weight for _, weight in weighted_scores)
            overall = sum(score * weight for score, weight in weighted_scores) / total_weight
        else:
            overall = cls._fallback_completion_score(activity)

        if cardiac_decoupling > 0.08:
            overall *= 0.90
        elif cardiac_decoupling > 0.05:
            overall *= 0.95

        breakdown = {
            "actual_pace_sec_per_km": actual_pace,
            "actual_avg_hr": actual_hr,
            "actual_duration_min": actual_duration,
            "actual_distance_km": actual_distance,
            "prescribed": prescribed,
            "cardiac_decoupling": cardiac_decoupling,
        }

        return ComplianceResult(
            overall_score=round(max(0.0, min(1.0, overall)), 3),
            pace_score=pace_score,
            hr_score=hr_score,
            duration_score=duration_score,
            distance_score=distance_score,
            cardiac_decoupling=cardiac_decoupling,
            breakdown=breakdown,
        )

    @staticmethod
    def compute_cardiac_decoupling(splits: list) -> float:
        valid = []
        for split in splits or []:
            distance = split.get("distance", 0) or split.get("distance_km", 0)
            elapsed = split.get("elapsed_time", 0) or split.get("moving_time", 0)
            hr = split.get("average_heartrate") or split.get("avg_heart_rate") or split.get("average_hr")
            if distance and elapsed and hr and elapsed > 0 and hr > 0:
                distance_km = distance / 1000.0 if distance > 100 else distance
                pace_efficiency = (distance_km / (elapsed / 60.0)) / hr
                valid.append(pace_efficiency)

        if len(valid) < 4:
            return 0.0

        midpoint = len(valid) // 2
        first = sum(valid[:midpoint]) / len(valid[:midpoint])
        second = sum(valid[midpoint:]) / len(valid[midpoint:])
        if first <= 0:
            return 0.0
        return round(max(0.0, (first - second) / first), 4)

    @staticmethod
    def _pace_seconds_per_km(distance_km: Optional[float], moving_time_min: Optional[float]) -> Optional[float]:
        if not distance_km or not moving_time_min or distance_km <= 0 or moving_time_min <= 0:
            return None
        return round((moving_time_min * 60.0) / distance_km, 1)

    @staticmethod
    def _target_score(actual: Optional[float], target: Optional[float], tolerance_pct: float, lower_is_better: bool = False) -> Optional[float]:
        if actual is None or target is None or target <= 0:
            return None
        tolerance = max(0.01, tolerance_pct or 0.10)
        deviation = abs(actual - target) / target
        if lower_is_better and actual < target:
            deviation *= 0.50
        return round(max(0.0, 1.0 - (deviation / tolerance) * 0.50), 3)

    @staticmethod
    def _range_score(actual: Optional[float], low: Optional[float], high: Optional[float]) -> Optional[float]:
        if actual is None or low is None or high is None or high <= low:
            return None
        if low <= actual <= high:
            return 1.0
        nearest = low if actual < low else high
        deviation = abs(actual - nearest) / nearest if nearest else 1.0
        return round(max(0.0, 1.0 - deviation * 4.0), 3)

    @staticmethod
    def _fallback_completion_score(activity: Any) -> float:
        if not activity.moving_time_min or not activity.distance_km:
            return 0.0
        if (activity.avg_heart_rate or 0) > 0 or (activity.perceived_exertion_rpe or 0) > 0:
            return 0.85
        return 0.70
