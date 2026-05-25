"""
Phase 9: Multi-Sport Support
Cycling, swimming, and cross-training metric calculations
"""
import logging
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SportType(Enum):
    RUNNING = "run"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    CROSS_TRAINING = "cross_training"


class CyclingMetricsCalculator:
    """
    Cycling-specific metrics: power zones, watts/kg, cadence
    """

    @staticmethod
    def calculate_power_zones(threshold_watts: float) -> Dict[int, tuple]:
        """
        Calculate cycling power zones based on threshold power.
        Zone 1: Recovery (< 55%)
        Zone 2: Endurance (55-75%)
        Zone 3: Tempo (75-90%)
        Zone 4: VO2Max (90-105%)
        Zone 5: Anaerobic (105-120%)
        Zone 6: Neuromuscular (> 120%)
        """
        return {
            1: (0, int(threshold_watts * 0.55), "Recovery"),
            2: (int(threshold_watts * 0.55), int(threshold_watts * 0.75), "Endurance"),
            3: (int(threshold_watts * 0.75), int(threshold_watts * 0.90), "Tempo"),
            4: (int(threshold_watts * 0.90), int(threshold_watts * 1.05), "VO2Max"),
            5: (int(threshold_watts * 1.05), int(threshold_watts * 1.20), "Anaerobic"),
            6: (int(threshold_watts * 1.20), 999999, "Neuromuscular")
        }

    @staticmethod
    def calculate_tss_cycling(power_data: Dict, athlete_weight_kg: float) -> float:
        """
        Cycling TSS: (IF^2) × hours × 100
        where IF = avg_power / threshold_power
        """
        avg_power = power_data.get("avg_power", 0)
        duration_seconds = power_data.get("duration", 0)
        threshold_power = power_data.get("threshold_power", 250)

        if not avg_power or not duration_seconds:
            return 0

        hours = duration_seconds / 3600
        if_value = avg_power / threshold_power
        tss = (if_value ** 2) * hours * 100

        return min(tss, 600)

    @staticmethod
    def calculate_watts_per_kg(power: float, athlete_weight_kg: float) -> float:
        """Calculate relative power (watts/kg)"""
        if not athlete_weight_kg:
            return 0
        return power / athlete_weight_kg


class SwimmingMetricsCalculator:
    """
    Swimming-specific metrics: pace zones, stroke rate, efficiency
    """

    @staticmethod
    def calculate_pace_zones(threshold_pace_seconds_per_100m: float) -> Dict[int, tuple]:
        """
        Calculate swimming pace zones (in seconds per 100m).
        Zone 1: Recovery (> 150% threshold)
        Zone 2: Endurance (125-150% threshold)
        Zone 3: Steady (100-125% threshold)
        Zone 4: Tempo (85-100% threshold)
        Zone 5: Threshold (70-85% threshold)
        Zone 6: Maximum (< 70% threshold)
        """
        return {
            1: (threshold_pace_seconds_per_100m * 1.50, 999, "Recovery"),
            2: (threshold_pace_seconds_per_100m * 1.25, threshold_pace_seconds_per_100m * 1.50, "Endurance"),
            3: (threshold_pace_seconds_per_100m * 1.00, threshold_pace_seconds_per_100m * 1.25, "Steady"),
            4: (threshold_pace_seconds_per_100m * 0.85, threshold_pace_seconds_per_100m * 1.00, "Tempo"),
            5: (threshold_pace_seconds_per_100m * 0.70, threshold_pace_seconds_per_100m * 0.85, "Threshold"),
            6: (0, threshold_pace_seconds_per_100m * 0.70, "Maximum")
        }

    @staticmethod
    def calculate_tss_swimming(swim_data: Dict) -> float:
        """
        Swimming TSS based on distance and pace intensity.
        TSS = (pace_intensity_factor^2) × duration_hours × 100
        """
        distance_meters = swim_data.get("distance", 0)
        duration_seconds = swim_data.get("duration", 0)
        avg_pace_seconds_per_100m = swim_data.get("avg_pace", 120)  # Default 2 min/100m
        threshold_pace = swim_data.get("threshold_pace", 90)

        if not distance_meters or not duration_seconds:
            return 0

        hours = duration_seconds / 3600
        intensity_factor = threshold_pace / avg_pace_seconds_per_100m
        tss = (intensity_factor ** 2) * hours * 100

        return min(tss, 400)

    @staticmethod
    def calculate_swim_efficiency(distance_meters: float, stroke_count: int) -> float:
        """
        Calculate stroke efficiency (distance per stroke).
        Higher = more efficient
        """
        if not stroke_count:
            return 0
        return distance_meters / stroke_count


class CrossTrainingCalculator:
    """
    Cross-training (strength, yoga, mobility, etc.)
    """

    @staticmethod
    def calculate_cross_training_tss(activity_type: str, duration_seconds: int, intensity: str) -> float:
        """
        Cross-training TSS based on activity type and intensity.
        Intensity: low (1.0), moderate (1.5), high (2.0)
        """
        intensity_multiplier = {
            "low": 1.0,
            "moderate": 1.5,
            "high": 2.0
        }.get(intensity.lower(), 1.0)

        hours = duration_seconds / 3600
        base_tss = hours * 100 * intensity_multiplier

        # Activity-specific adjustments
        activity_multiplier = {
            "strength": 1.2,
            "yoga": 0.8,
            "mobility": 0.9,
            "pilates": 1.1,
            "hiit": 1.5,
            "circuit": 1.3
        }.get(activity_type.lower(), 1.0)

        return base_tss * activity_multiplier


class MultiSportMetricsEngine:
    """
    Unified metrics engine for all sports
    """

    @staticmethod
    def calculate_universal_tss(activity_data: Dict) -> float:
        """
        Calculate TSS for any sport type.
        Dispatches to sport-specific calculator.
        """
        sport_type = activity_data.get("sport", "running").lower()

        if "cycling" in sport_type or "bike" in sport_type:
            return CyclingMetricsCalculator.calculate_tss_cycling(activity_data, activity_data.get("weight_kg", 70))
        elif "swim" in sport_type:
            return SwimmingMetricsCalculator.calculate_tss_swimming(activity_data)
        elif any(x in sport_type for x in ["strength", "yoga", "mobility", "pilates"]):
            return CrossTrainingCalculator.calculate_cross_training_tss(
                sport_type,
                activity_data.get("duration", 0),
                activity_data.get("intensity", "moderate")
            )
        else:
            # Default to running TSS
            return MultiSportMetricsEngine._calculate_default_tss(activity_data)

    @staticmethod
    def _calculate_default_tss(activity_data: Dict) -> float:
        """Running TSS formula (HR-based)"""
        avg_hr = activity_data.get("avg_hr", 0)
        duration_seconds = activity_data.get("duration", 0)
        threshold_hr = activity_data.get("threshold_hr", 165)

        if not avg_hr or not duration_seconds:
            return 0

        hours = duration_seconds / 3600
        intensity_factor = avg_hr / threshold_hr
        tss = (intensity_factor ** 2) * hours * 100

        return min(tss, 500)

    @staticmethod
    def get_sport_zones(sport_type: str, athlete_data: Dict) -> Dict:
        """Get appropriate zones for sport type"""
        if "cycling" in sport_type.lower():
            threshold_power = athlete_data.get("threshold_power", 250)
            return CyclingMetricsCalculator.calculate_power_zones(threshold_power)
        elif "swim" in sport_type.lower():
            threshold_pace = athlete_data.get("threshold_pace_swim", 90)
            return SwimmingMetricsCalculator.calculate_pace_zones(threshold_pace)
        else:
            # Running zones (HR-based)
            return {
                1: (0, int(athlete_data.get("max_hr", 190) * 0.60), "Zone 1"),
                2: (int(athlete_data.get("max_hr", 190) * 0.60), int(athlete_data.get("max_hr", 190) * 0.75), "Zone 2"),
                3: (int(athlete_data.get("max_hr", 190) * 0.75), int(athlete_data.get("max_hr", 190) * 0.85), "Zone 3"),
                4: (int(athlete_data.get("max_hr", 190) * 0.85), int(athlete_data.get("max_hr", 190) * 0.95), "Zone 4"),
                5: (int(athlete_data.get("max_hr", 190) * 0.95), 220, "Zone 5"),
            }
