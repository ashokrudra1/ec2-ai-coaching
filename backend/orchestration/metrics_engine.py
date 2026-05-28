# backend/orchestration/metrics_engine.py
"""
Advanced Sports-Science Metrics Engine

Pure Python calculations (no LLM dependency) for:
- CTL/ATL/TSB (Training Load Metrics)
- ACWR (Acute-to-Chronic Workload Ratio)
- Heart Rate Drift Analysis
- Cadence Degradation Detection
- Race Time Prediction (Riegel Formula adjusted)

Author: Veda AI Elite Architecture Team
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

class WorkoutDataPoint(BaseModel):
    """Represents a single workout"""
    date: datetime
    tss: float  # Training Stress Score
    duration_min: float
    distance_km: float
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    avg_cadence: Optional[float] = None


class TrainingMetrics(BaseModel):
    """Aggregated training metrics"""
    ctl: float  # Chronic Training Load (42-day)
    atl: float  # Acute Training Load (7-day)
    tsb: float  # Training Stress Balance (CTL - ATL)
    acwr: float  # Acute-to-Chronic Workload Ratio (ATL / CTL)
    injury_risk: str  # 'low', 'moderate', 'high'
    form_score: float  # -10 to +10, higher is better
    fatigue_level: str  # 'rested', 'normal', 'fatigued', 'overreached'


class SafetyCheckResult(BaseModel):
    """Result of safety/conflict checks"""
    override_active: bool
    reason: Optional[str] = None
    suggested_intensity: str  # 'rest', 'active_recovery', 'z2_aerobic', 'normal', 'hard'
    medical_restrictions: List[str]
    tsb_warning: Optional[str] = None
    acwr_warning: Optional[str] = None


# ============================================================================
# METRICS ENGINE
# ============================================================================

class TrainingMetricsEngine:
    """
    Pure programmatic calculation of training stress metrics.
    
    All calculations use exponential decay models from Training Peaks methodology.
    """
    
    # Exponential decay constants
    CTL_DECAY_DAYS = 42
    ATL_DECAY_DAYS = 7
    
    # CTL alpha: ~0.0222 (decay constant for 42-day halflife)
    # ATL alpha: ~0.1429 (decay constant for 7-day halflife)
    CTL_ALPHA = 1.0 / (CTL_DECAY_DAYS + 1)
    ATL_ALPHA = 1.0 / (ATL_DECAY_DAYS + 1)
    
    @classmethod
    def calculate_metrics(
        cls,
        workouts: List[WorkoutDataPoint],
        current_ctl: Optional[float] = None,
        current_atl: Optional[float] = None
    ) -> TrainingMetrics:
        """
        Calculate comprehensive training metrics from workout history.
        
        Args:
            workouts: List of WorkoutDataPoint sorted by date (oldest first)
            current_ctl: Previous CTL value (for incremental calculation)
            current_atl: Previous ATL value (for incremental calculation)
            
        Returns:
            TrainingMetrics object with CTL, ATL, TSB, ACWR, injury risk
        """
        if not workouts:
            logger.warning("No workouts provided for metrics calculation")
            return TrainingMetrics(
                ctl=0.0,
                atl=0.0,
                tsb=0.0,
                acwr=0.0,
                injury_risk="low",
                form_score=0.0,
                fatigue_level="rested"
            )
        
        # Sort workouts by date (ensure chronological order)
        workouts_sorted = sorted(workouts, key=lambda w: w.date)
        
        # Initialize or use provided values
        ctl = current_ctl or 0.0
        atl = current_atl or 0.0
        
        # Iterative exponential decay calculation
        for workout in workouts_sorted:
            tss = workout.tss
            
            # Update CTL: exponential moving average (42-day halflife)
            ctl = ctl + cls.CTL_ALPHA * (tss - ctl)
            
            # Update ATL: exponential moving average (7-day halflife)
            atl = atl + cls.ATL_ALPHA * (tss - atl)
        
        # Calculate TSB (Training Stress Balance = Form)
        tsb = ctl - atl
        
        # Calculate ACWR (Acute-to-Chronic Workload Ratio)
        acwr = atl / ctl if ctl > 0 else 0.0
        
        # Determine injury risk based on ACWR
        injury_risk = cls._assess_injury_risk(acwr)
        
        # Calculate form score (-10 to +10)
        # TSB > 10 = excellent form, TSB < -20 = overreached
        form_score = max(-10, min(10, tsb / 5.0))
        
        # Determine fatigue level
        fatigue_level = cls._assess_fatigue(tsb)
        
        logger.info(
            f"📊 Metrics: CTL={ctl:.1f}, ATL={atl:.1f}, TSB={tsb:.1f}, "
            f"ACWR={acwr:.2f}, Injury Risk={injury_risk}, Form={form_score:.1f}"
        )
        
        return TrainingMetrics(
            ctl=round(ctl, 2),
            atl=round(atl, 2),
            tsb=round(tsb, 2),
            acwr=round(acwr, 2),
            injury_risk=injury_risk,
            form_score=round(form_score, 1),
            fatigue_level=fatigue_level
        )
    
    
    @classmethod
    def _assess_injury_risk(cls, acwr: float) -> str:
        """
        Assess injury risk based on ACWR (Acute-to-Chronic ratio).
        
        Research indicates:
        - ACWR > 1.5: Very high injury risk
        - ACWR 1.2-1.5: High injury risk
        - ACWR 0.8-1.2: Optimal zone
        - ACWR < 0.8: Insufficient training stimulus (detraining risk)
        """
        if acwr > 1.5:
            return "high"
        elif acwr >= 1.2:
            return "moderate"
        elif acwr >= 0.8:
            return "low"
        else:
            return "low"  # Detraining risk, but not acute injury
    
    
    @classmethod
    def _assess_fatigue(cls, tsb: float) -> str:
        """
        Assess fatigue level based on TSB.
        
        - TSB > 10: Rested (fresh legs)
        - TSB 0 to 10: Normal
        - TSB -10 to 0: Fatigued
        - TSB < -20: Overreached (needs immediate recovery)
        """
        if tsb > 10:
            return "rested"
        elif tsb >= 0:
            return "normal"
        elif tsb >= -10:
            return "fatigued"
        else:
            return "overreached"
    
    
    @classmethod
    def predict_race_time(
        cls,
        current_pace_5k_sec: float,
        vo2_max_percent: float = 1.0,
        ctl_strain_factor: float = 1.0,
        target_distance_km: float = 10.0,
        reference_distance_km: float = 5.0
    ) -> float:
        """
        Predict race time using Riegel's formula adjusted for VO2Max and CTL strain.
        
        Riegel's Formula: t2 = t1 * (d2/d1)^1.06
        
        Args:
            current_pace_5k_sec: Current 5K pace in seconds
            vo2_max_percent: VO2Max trend (1.0 = stable, 1.1 = +10%, 0.95 = -5%)
            ctl_strain_factor: CTL fatigue adjustment (1.0 = normal, 0.95 = fatigued)
            target_distance_km: Target race distance (e.g., 10K, HM, marathon)
            reference_distance_km: Reference distance (default 5K)
            
        Returns:
            Predicted race pace in seconds
        """
        # Base Riegel calculation
        riegel_exponent = 1.06
        distance_ratio = target_distance_km / reference_distance_km
        predicted_pace = current_pace_5k_sec * (distance_ratio ** riegel_exponent)
        
        # Apply VO2Max adjustment (improved fitness = faster pace)
        predicted_pace = predicted_pace / vo2_max_percent
        
        # Apply CTL strain adjustment (fatigue = slower pace)
        predicted_pace = predicted_pace / ctl_strain_factor
        
        logger.info(
            f"🏃 Race Prediction: {current_pace_5k_sec:.0f}s/km (5K) → "
            f"{predicted_pace:.0f}s/km ({target_distance_km}K), "
            f"VO2Max adj={vo2_max_percent:.2f}, CTL adj={ctl_strain_factor:.2f}"
        )
        
        return round(predicted_pace, 1)
    
    
    @classmethod
    def analyze_hr_drift(
        cls,
        hr_data_over_time: List[tuple]  # [(time_min, hr_bpm), ...]
    ) -> Dict[str, float]:
        """
        Analyze Heart Rate Drift (cardiovascular decoupling).
        
        HR Drift > 5% indicates fatigue/poor aerobic form.
        HR Drift < 5% indicates good aerobic efficiency.
        
        Args:
            hr_data_over_time: List of (time_minutes, heart_rate) tuples
            
        Returns:
            Dict with drift_percent, first_half_avg_hr, second_half_avg_hr
        """
        if not hr_data_over_time or len(hr_data_over_time) < 2:
            return {"drift_percent": 0.0, "first_half_avg_hr": 0, "second_half_avg_hr": 0}
        
        midpoint = len(hr_data_over_time) // 2
        first_half = [hr for _, hr in hr_data_over_time[:midpoint]]
        second_half = [hr for _, hr in hr_data_over_time[midpoint:]]
        
        avg_hr_first = sum(first_half) / len(first_half)
        avg_hr_second = sum(second_half) / len(second_half)
        
        drift_percent = ((avg_hr_second - avg_hr_first) / avg_hr_first) * 100
        
        logger.info(
            f"❤️  HR Drift: {avg_hr_first:.0f} → {avg_hr_second:.0f} BPM "
            f"({drift_percent:+.1f}%, {'Aerobic fatigue' if drift_percent > 5 else 'Efficient'})"
        )
        
        return {
            "drift_percent": round(drift_percent, 1),
            "first_half_avg_hr": round(avg_hr_first, 1),
            "second_half_avg_hr": round(avg_hr_second, 1),
            "efficiency_status": "poor" if drift_percent > 5 else "good"
        }
    
    
    @classmethod
    def analyze_cadence_collapse(
        cls,
        cadence_data_over_time: List[tuple]  # [(time_min, cadence_rpm), ...]
    ) -> Dict[str, float]:
        """
        Analyze cadence collapse (mechanical degradation).
        
        Cadence loss > 10% indicates fatigue/form breakdown.
        
        Args:
            cadence_data_over_time: List of (time_minutes, cadence_rpm) tuples
            
        Returns:
            Dict with collapse_percent, initial_cadence, final_cadence
        """
        if not cadence_data_over_time or len(cadence_data_over_time) < 2:
            return {"collapse_percent": 0.0, "initial_cadence": 0, "final_cadence": 0}
        
        initial_cadence = cadence_data_over_time[0][1]
        final_cadence = cadence_data_over_time[-1][1]
        
        collapse_percent = ((initial_cadence - final_cadence) / initial_cadence) * 100
        
        logger.info(
            f"⚙️  Cadence Collapse: {initial_cadence:.0f} → {final_cadence:.0f} RPM "
            f"({-collapse_percent:+.1f}%)"
        )
        
        return {
            "collapse_percent": round(collapse_percent, 1),
            "initial_cadence": round(initial_cadence, 1),
            "final_cadence": round(final_cadence, 1),
            "mechanical_status": "degraded" if collapse_percent > 10 else "maintained"
        }
