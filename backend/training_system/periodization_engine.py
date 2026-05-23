# backend/training_system/periodization_engine.py
import math
import logging
from datetime import datetime, timedelta
from backend.models import User, Activity

logger = logging.getLogger(__name__)

class PeriodizationEngine:
    """
    Algorithmic Training Periodization and Overload System.
    Manages macrocycles, mesocycles, progression blocks, and race taper decay curves.
    """

    @staticmethod
    def calculate_macrocycle_phase(user: User, race_date: datetime) -> str:
        """
        Determines the current training macrocycle based on the time remaining until race day.
        """
        if not race_date:
            return "Base"
        
        days_to_race = (race_date - datetime.utcnow()).days
        weeks_to_race = math.ceil(days_to_race / 7.0)

        if weeks_to_race <= 0:
            return "Recovery"
        elif weeks_to_race <= 1:
            return "Race Week"
        elif weeks_to_race <= 3:
            return "Taper"
        elif weeks_to_race <= 8:
            return "Peak"
        elif weeks_to_race <= 16:
            return "Build"
        else:
            return "Base"

    @staticmethod
    def calculate_weekly_tss_target(user: User, historical_activities: list) -> float:
        """
        Sets the weekly training load target (TSS) using periodized overload patterns.
        Applies a 3-week build followed by a 1-week deload structure.
        """
        if not historical_activities:
            return user.target_weekly_tss or 150.0

        # Calculate the athlete's 3-week rolling baseline load
        recent_3_weeks = [a for a in historical_activities if a.start_date_utc >= datetime.utcnow() - timedelta(days=21)]
        if not recent_3_weeks:
            return user.target_weekly_tss or 150.0

        baseline_avg_weekly_tss = sum(a.training_stress_score_tss or 0.0 for a in recent_3_weeks) / 3.0
        week_num = (user.macrocycle_week % 4) or 4 # 1, 2, 3 (Build Weeks), 4 (Deload Week)

        phase = user.training_phase or "Base"
        fatigue_accumulation = user.fatigue_accumulation_rate or 1.0

        # Run periodized load step-ups based on the current week
        if week_num == 1:
            # Step up target relative to rolling baseline
            target_tss = baseline_avg_weekly_tss * 1.05
        elif week_num == 2:
            # Overload Step-up 1
            target_tss = baseline_avg_weekly_tss * 1.12
        elif week_num == 3:
            # Overload Step-up 2 (Max Overload)
            target_tss = baseline_avg_weekly_tss * 1.18 * (1.0 / fatigue_accumulation)
        else:
            # Deload/Recovery Week (Drop load to consolidate gains)
            target_tss = baseline_avg_weekly_tss * 0.70

        # Cap the target to prevent sudden workload spikes (> 20% week-on-week load jumps)
        max_safe_limit = baseline_avg_weekly_tss * 1.22
        final_target = min(max_safe_limit, max(100.0, target_tss))
        return round(final_target, 1)

    @staticmethod
    def calculate_race_taper_decay(weeks_to_race: int, baseline_volume_km: float) -> float:
        """
        Calculates exponential taper decay to shed physiological fatigue while maintaining
        neuromuscular sharpness before race day.
        Formula: V_taper = V_baseline * e^(-0.25 * t)
        """
        if weeks_to_race <= 0:
            return 0.0
        # Exponential volume reduction coefficient
        decay_factor = math.exp(-0.25 * (3.0 - weeks_to_race))
        return round(baseline_volume_km * max(0.40, min(1.0, decay_factor)), 1)
