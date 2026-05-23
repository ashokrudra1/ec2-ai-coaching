# backend/analytics.py
import logging
import math
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from backend.models import User, Activity

logger = logging.getLogger(__name__)

def compute_cardiac_decoupling(splits: list, avg_hr: float) -> float:
    if not splits or len(splits) < 4 or not avg_hr or avg_hr <= 0:
        return 0.0
    try:
        midpoint = len(splits) // 2
        first_half = splits[:midpoint]
        second_half = splits[midpoint:]

        first_half_ef = sum((s.get("distance", 0) / (s.get("elapsed_time", 1) / 60.0)) / avg_hr for s in first_half if s.get("elapsed_time", 0) > 0) / len(first_half)
        second_half_ef = sum((s.get("distance", 0) / (s.get("elapsed_time", 1) / 60.0)) / avg_hr for s in second_half if s.get("elapsed_time", 0) > 0) / len(second_half)

        if first_half_ef <= 0: return 0.0
        return round(max(0.0, (first_half_ef - second_half_ef) / first_half_ef), 3)
    except Exception:
        return 0.0

def compute_cadence_degradation(splits: list) -> float:
    if not splits or len(splits) < 3:
        return 0.0
    try:
        first_cadence = splits[0].get("average_cadence", 170.0)
        last_cadence = splits[-1].get("average_cadence", 170.0)
        if not first_cadence or first_cadence <= 0 or not last_cadence or last_cadence <= 0:
            return 0.0
        return round(max(0.0, (first_cadence - last_cadence) / first_cadence), 3)
    except Exception:
        return 0.0

def compute_glycogen_depletion(distance_km: float, moving_time_min: float, user_weight_kg: float = 72.0) -> float:
    if not distance_km or not moving_time_min or moving_time_min <= 0:
        return 0.0
    try:
        speed_kmh = (distance_km / moving_time_min) * 60.0
        met = (0.2 * (speed_kmh * 16.67) + 3.5) / 3.5
        total_kcal = met * user_weight_kg * (moving_time_min / 60.0)
        return round(max(0.0, (total_kcal * 0.60) / 4.1), 1)
    except Exception:
        return 0.0

def compute_grade_adjusted_tss(activity: Activity, user: User) -> float:
    duration = activity.moving_time_min or 0.0
    if duration <= 0: return 0.0
    try:
        avg_hr = activity.avg_heart_rate
        rpe = activity.perceived_exertion_rpe or 5
        rpe_intensity = rpe / 10.0

        if not avg_hr or not user.max_hr or not user.rest_hr:
            return round((duration * rpe_intensity * (rpe_intensity * 100)) / 60.0, 1)

        hr_reserve = user.max_hr - user.rest_hr
        if hr_reserve <= 0:
            return round((duration * rpe_intensity * (rpe_intensity * 100)) / 60.0, 1)

        hr_intensity = max(0.4, min(1.0, (avg_hr - user.rest_hr) / hr_reserve))

        elevation_gain = activity.total_elevation_gain or 0.0
        distance = activity.distance_km or 1.0
        vert_gain_ratio = elevation_gain / distance
        grade_multiplier = 1.0 + (vert_gain_ratio / 500.0)
        adjusted_intensity = min(1.0, hr_intensity * grade_multiplier)

        temp_c = activity.temperature_c or 20.0
        if temp_c > 28.0:
            heat_penalty = 1.0 + ((temp_c - 28.0) * 0.015)
            adjusted_intensity = min(1.0, adjusted_intensity * heat_penalty)

        return round((duration * adjusted_intensity * (adjusted_intensity * 100)) / 60.0, 1)
    except Exception:
        return 0.0

def calculate_activity_tss(activity: Activity, user: User) -> float:
    return compute_grade_adjusted_tss(activity, user)

def get_fatigue_metrics(db: Session, user_id: int):
    user = db.query(User).filter_by(id=user_id).first()
    if not user: return 0.0, 0.0, 0.0, "No Data"

    atl = user.atl or 0.0
    ctl = user.ctl or 0.0
    tsb = user.tsb or 0.0

    if tsb < -20: status = "High Fatigue"
    elif -20 <= tsb < -5: status = "Optimal Training Stress"
    elif -5 <= tsb <= 10: status = "Baseline Balanced"
    else: status = "Fresh / Recovery Zone"

    return atl, ctl, tsb, status

def update_user_fitness_metrics(db: Session, user_id: int, activity_tss: float = 0.0):
    """
    Applies metrics via strict state decay logic with pessimistic 
    row-level database execution locks.
    """
    try:
        # 🔐 CONCURRENCY FIX: Hold update thread exclusively to eliminate duplicate webhook race hazards
        user = db.query(User).filter_by(id=user_id).with_for_update().first()
        if not user: return

        ctl_decay = math.exp(-1.0 / 42.0)
        atl_decay = math.exp(-1.0 / 7.0)

        current_ctl = (user.ctl or 0.0) * ctl_decay
        current_atl = (user.atl or 0.0) * atl_decay

        if activity_tss > 0.0:
            current_ctl += activity_tss * (1.0 - ctl_decay)
            current_atl += activity_tss * (1.0 - atl_decay)

        user.ctl = round(current_ctl, 1)
        user.atl = round(current_atl, 1)
        
        # 🏃‍♂️ SPORTS SCIENCE MODEL CORRECTION: Pure Banister calculation formula mapping
        user.tsb = round(user.ctl - user.atl, 1)

        db.add(user)
        db.commit()
        logger.info(f"💾 Incremental fitness metrics written: CTL={user.ctl}, ATL={user.atl}, TSB={user.tsb}")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Incremental load calculation crashed: {str(e)}")
