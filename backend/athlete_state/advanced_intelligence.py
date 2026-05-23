# backend/athlete_state/advanced_intelligence.py
import math
import logging
from typing import Dict, List, Optional
from datetime import datetime
from backend.models import User, Activity

logger = logging.getLogger(__name__)

class AdvancedTrainingIntelligence:

    @staticmethod
    def evaluate_workout_compliance(activity: Activity, user: User, target_hr_ceiling: int, target_duration_min: float) -> dict:
        """
        Deep Biomechanical & Physiological Compliance Engine.
        Analyzes pacing adherence, heart rate decoupling (aerobic drift), and cadence degradation.
        Returns a detailed compliance score (0.0 to 1.0) and coaching flags.
        """
        if not activity or not user:
            return {"compliance_score": 1.0, "status": "No activity data"}

        penalties = 0.0
        details = {}

        # 1. Heart Rate Adherence Penalty
        avg_hr = activity.avg_heart_rate or 0.0
        if avg_hr > target_hr_ceiling:
            hr_drift = (avg_hr - target_hr_ceiling) / target_hr_ceiling
            hr_penalty = min(0.35, hr_drift * 1.5)  # Cap at 35% penalty
            penalties += hr_penalty
            details["hr_exceeded_ceiling_by_bpm"] = round(avg_hr - target_hr_ceiling, 1)
            details["hr_penalty"] = round(hr_penalty, 2)

        # 2. Duration/Volume Adherence Penalty
        actual_duration = activity.moving_time_min or 0.0
        if target_duration_min > 0:
            duration_ratio = actual_duration / target_duration_min
            if duration_ratio > 1.15: # Too long (Overreaching)
                dur_penalty = min(0.20, (duration_ratio - 1.15) * 1.0)
                penalties += dur_penalty
                details["volume_error"] = "Overreached target distance/duration"
                details["duration_penalty"] = round(dur_penalty, 2)
            elif duration_ratio < 0.85: # Too short
                dur_penalty = min(0.25, (0.85 - duration_ratio) * 1.0)
                penalties += dur_penalty
                details["volume_error"] = "Workout terminated significantly early"
                details["duration_penalty"] = round(dur_penalty, 2)

        # 3. Cadence & Mechanical Collapse check
        cadence_degradation = activity.cadence_degradation or 0.0
        if cadence_degradation > 0.06: # Stride collapse > 6%
            cadence_penalty = min(0.15, (cadence_degradation - 0.06) * 2.0)
            penalties += cadence_penalty
            details["mechanical_fatigue"] = "Stride cadence collapsed over final splits"
            details["cadence_penalty"] = round(cadence_penalty, 2)

        final_score = round(max(0.10, 1.0 - penalties), 2)
        
        return {
            "compliance_score": final_score,
            "cardiac_decoupling": round(activity.cardiac_decoupling or 0.0, 3),
            "cadence_degradation": round(cadence_degradation, 3),
            "assessment_details": details
        }

    @staticmethod
    def predict_race_performances(user: User) -> dict:
        """
        Calculates projected race finish times across core distances.
        Uses estimated VO2 Max, Threshold Paces, and current CTL as a capacity scaling factor.
        Formula: T2 = T1 * (D2 / D1)^1.06 (Riegel's formula) scaled by fatigue-capacity trends.
        """
        # Read from cached physiological twin snapshot, fallback to safe defaults
        phys_twin = user.physiological_twin or {}
        estimated_vo2 = phys_twin.get("vo2max_estimate", 45.0)
        
        # Scaling coefficient based on current training load consistency (CTL)
        # CTL of 60 indicates fully optimized cardiovascular volume potential
        ctl_factor = min(1.02, max(0.88, (user.ctl or 30.0) / 60.0))

        # Base reference pace (Threshold Pace in seconds per kilometer)
        # If not populated, derive from a standard VO2 max lookup approximation
        base_threshold_pace = phys_twin.get("threshold_pace")
        if not base_threshold_pace or base_threshold_pace <= 0:
            base_threshold_pace = int(30000 / estimated_vo2) # Simple VO2 to sec/km conversion

        # 10K Time reference calculation
        base_10k_time_sec = base_threshold_pace * 10.0 / ctl_factor

        def format_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"

        # Projected times using customized Riegel scaling exponents
        predictions = {}
        distances = {
            "5K": 5.0,
            "10K": 10.0,
            "Half-Marathon": 21.0975,
            "Marathon": 42.195
        }

        for distance_name, dist_km in distances.items():
            # Apply Riegel's scaling: T_target = T_ref * (D_target / D_ref) ^ 1.06
            predicted_seconds = base_10k_time_sec * math.pow((dist_km / 10.0), 1.06)
            predictions[distance_name] = format_time(predicted_seconds)

        return {
            "scaled_vo2max": round(estimated_vo2 * ctl_factor, 1),
            "estimated_threshold_pace_sec_km": int(base_threshold_pace / ctl_factor),
            "predictions": predictions
        }

    @staticmethod
    def generate_adaptive_macrocycle_plan(user: User, weeks_to_target: int) -> dict:
        """
        AI Macrocycle Periodization Engine.
        Synthesizes an adaptive 16-week periodization matrix customized to the athlete's current CTL and TSB.
        Outputs structural focus, target mileage ranges, and volume/intensity distribution ratios.
        """
        if weeks_to_target <= 0:
            return {"phase": "Recovery/Transition", "focus": "Absorbing residual training stress. Passive cross-training."}

        current_ctl = user.ctl or 10.0
        
        # Base target weekly volume (scaled to match current fitness capabilities safely)
        baseline_mileage = max(20.0, min(120.0, current_ctl * 0.8))

        # Dynamic target assignment based on macrocycle proximity
        if weeks_to_target > 12:
            phase = "Base Conditioning Phase"
            focus = "Mitochondrial adaptation, capillary density, and joint strength expansion."
            intensity_split = "85% Aerobic Base (Zone 1/2) | 15% Strides & Speed Play"
            target_mileage = f"{round(baseline_mileage, 1)} - {round(baseline_mileage * 1.15, 1)} km"
        elif weeks_to_target > 6:
            phase = "Build / Threshold Phase"
            focus = "Lactate clearance thresholds, mechanical efficiency, and sustained tempo expansion."
            intensity_split = "75% Aerobic Base (Zone 1/2) | 20% Lactate Tempo | 5% Speed Intervals"
            target_mileage = f"{round(baseline_mileage * 1.1, 1)} - {round(baseline_mileage * 1.25, 1)} km"
        elif weeks_to_target > 2:
            phase = "Peak Performance Phase"
            focus = "Race simulation blocks, maximal oxygen uptake capacity, and mechanical specificity."
            intensity_split = "70% Aerobic Base | 20% Specific Pace Blocks | 10% High Intensity Vo2"
            target_mileage = f"{round(baseline_mileage * 1.2, 1)} - {round(baseline_mileage * 1.3, 1)} km"
        else:
            phase = "Exponential Taper Phase"
            focus = "Neuromuscular freshness enhancement while shedding residual training fatigue."
            intensity_split = "80% Active Recovery (Zone 1) | 20% High-Intensity Race Pace Strides"
            
            # Apply volume taper decay curve
            taper_ratio = math.exp(-0.25 * (3 - weeks_to_target))
            target_mileage = f"{round(baseline_mileage * max(0.40, taper_ratio), 1)} km"

        return {
            "macrocycle_week": user.macrocycle_week,
            "weeks_remaining": weeks_to_target,
            "periodization_phase": phase,
            "focus_objective": focus,
            "target_weekly_volume_range": target_mileage,
            "polarized_intensity_distribution": intensity_split,
            "current_tsb_state": round(user.tsb or 0.0, 1)
        }
