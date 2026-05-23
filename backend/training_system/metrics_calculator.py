"""
Metrics Calculation Engine
Calculates CTL/ATL/TSB, VO2Max, HR Zones, Personal Records
Processes historical activities for athlete profiling
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models import User, Activity, PerformanceMetric, PersonalRecord
from backend.database import ReplicaSessionLocal

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """
    Calculates all performance metrics from activity data
    """

    # Constants
    AEROBIC_THRESHOLD_PACE = 380  # seconds per km (roughly 6:20/km)
    THRESHOLD_HR_RATIO = 0.87  # %max HR
    VO2MAX_BASELINE = 45.0  # Estimated baseline for untrained male
    
    @staticmethod
    def calculate_tss(distance_km: float, avg_hr: float, max_hr: float, moving_time_min: float) -> float:
        """
        Calculate Training Stress Score (TSS)
        Based on HR-based model: intensity factor × duration (in hours) × 100
        """
        if avg_hr == 0 or max_hr == 0:
            # Fallback: use time and distance
            return (distance_km / moving_time_min) * moving_time_min * 0.5

        threshold_hr = max_hr * MetricsCalculator.THRESHOLD_HR_RATIO
        
        if avg_hr <= 0:
            return 0

        intensity_factor = avg_hr / threshold_hr
        duration_hours = moving_time_min / 60.0
        tss = intensity_factor * intensity_factor * duration_hours * 100

        return round(tss, 1)

    @staticmethod
    def calculate_ctl_atl_tsb(
        db: Session, user_id: int, look_back_days: int = 90
    ) -> Tuple[float, float, float]:
        """
        Calculate Chronic Training Load (CTL), Acute Training Load (ATL), Training Stress Balance (TSB)
        
        CTL = 42-day exponential moving average (training stress)
        ATL = 7-day exponential moving average (recent stress)
        TSB = CTL - ATL (negative = fatigued, positive = recovered)
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=look_back_days)

            activities = (
                db.query(Activity)
                .filter(Activity.user_id == user_id, Activity.start_date_utc >= cutoff_date)
                .order_by(Activity.start_date_utc)
                .all()
            )

            if not activities:
                return 0.0, 0.0, 0.0

            # Calculate daily TSS
            daily_tss = {}
            for activity in activities:
                date_key = activity.start_date_utc.date()
                if date_key not in daily_tss:
                    daily_tss[date_key] = 0
                daily_tss[date_key] += activity.training_stress_score_tss

            # Calculate CTL (42-day EMA) and ATL (7-day EMA)
            ctl = 0.0
            atl = 0.0

            decay_ctl = 1.0 - (1.0 / 42.0)  # ~0.976
            decay_atl = 1.0 - (1.0 / 7.0)   # ~0.857

            sorted_dates = sorted(daily_tss.keys())

            for date in sorted_dates:
                tss = daily_tss[date]
                ctl = tss + decay_ctl * ctl
                atl = tss + decay_atl * atl

            tsb = ctl - atl

            return round(ctl, 1), round(atl, 1), round(tsb, 1)

        except Exception as e:
            logger.error(f"❌ CTL/ATL/TSB calculation error: {e}")
            return 0.0, 0.0, 0.0

    @staticmethod
    def estimate_vo2max(db: Session, user_id: int) -> float:
        """
        Estimate VO2Max from recent race performances
        Uses simple linear regression based on pace and age
        """
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return MetricsCalculator.VO2MAX_BASELINE

            # Get recent 5K+ runs (last 6 months)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
            race_activities = (
                db.query(Activity)
                .filter(
                    Activity.user_id == user_id,
                    Activity.distance_km >= 5.0,
                    Activity.start_date_utc >= cutoff_date,
                )
                .order_by(Activity.start_date_utc.desc())
                .limit(5)
                .all()
            )

            if not race_activities:
                return user.physiological_twin.get("vo2max_estimate", MetricsCalculator.VO2MAX_BASELINE)

            # Simple estimation: faster pace = higher VO2Max
            # VO2Max ≈ 15 * (pace_in_km_per_min) + age_factor
            pace_sum = 0
            for activity in race_activities:
                if activity.moving_time_min > 0:
                    pace_km_per_min = activity.distance_km / activity.moving_time_min
                    pace_sum += pace_km_per_min

            avg_pace = pace_sum / len(race_activities)
            estimated_vo2max = (avg_pace * 60) + (user.age if user.age else 30) * 0.1 + 20

            return round(estimated_vo2max, 1)

        except Exception as e:
            logger.error(f"❌ VO2Max estimation error: {e}")
            return MetricsCalculator.VO2MAX_BASELINE

    @staticmethod
    def calculate_hr_zones(user: User) -> Dict[str, Tuple[int, int]]:
        """
        Calculate 5 HR zones based on max_hr and threshold_hr
        
        Zone 1 (Recovery): 50-60% max HR
        Zone 2 (Endurance): 60-70% max HR
        Zone 3 (Tempo): 70-80% max HR
        Zone 4 (Threshold): 80-90% max HR
        Zone 5 (VO2Max): 90-100% max HR
        """
        max_hr = user.max_hr or 190.0
        threshold_hr = max_hr * 0.87  # 87% of max

        zones = {
            "z1": (int(max_hr * 0.50), int(max_hr * 0.60)),
            "z2": (int(max_hr * 0.60), int(max_hr * 0.70)),
            "z3": (int(max_hr * 0.70), int(max_hr * 0.80)),
            "z4": (int(max_hr * 0.80), int(max_hr * 0.90)),
            "z5": (int(max_hr * 0.90), int(max_hr * 1.00)),
        }

        logger.info(f"HR Zones for user {user.id} (Max HR: {max_hr}): {zones}")

        return zones

    @staticmethod
    def calculate_personal_records(db: Session, user_id: int) -> Dict[str, Dict]:
        """
        Extract and calculate personal records by distance
        """
        try:
            pr_distances = [1.0, 5.0, 10.0, 21.1, 42.2]  # 1K, 5K, 10K, HM, Marathon
            personal_records = {}

            for distance in pr_distances:
                # Find fastest activity for this distance (±1km tolerance)
                fastest = (
                    db.query(Activity)
                    .filter(
                        Activity.user_id == user_id,
                        Activity.distance_km >= distance - 1.0,
                        Activity.distance_km <= distance + 1.0,
                    )
                    .order_by(Activity.moving_time_min.asc())
                    .first()
                )

                if fastest:
                    pace = fastest.moving_time_min / fastest.distance_km
                    minutes, seconds = divmod(int(pace * 60), 60)

                    personal_records[f"{distance}k"] = {
                        "distance": fastest.distance_km,
                        "time_seconds": int(fastest.moving_time_min * 60),
                        "pace_min_per_km": minutes,
                        "pace_sec": seconds,
                        "activity_id": fastest.id,
                        "activity_date": fastest.start_date_utc.isoformat(),
                    }

            return personal_records

        except Exception as e:
            logger.error(f"❌ Personal records calculation error: {e}")
            return {}

    @staticmethod
    def analyze_training_age(db: Session, user_id: int) -> int:
        """
        Estimate training age (years) from activity history
        """
        try:
            oldest_activity = (
                db.query(Activity)
                .filter(Activity.user_id == user_id)
                .order_by(Activity.start_date_utc.asc())
                .first()
            )

            if not oldest_activity:
                return 0

            days_since_start = (datetime.now(timezone.utc) - oldest_activity.start_date_utc).days
            training_age_years = max(0, days_since_start // 365)

            return training_age_years

        except Exception as e:
            logger.error(f"❌ Training age analysis error: {e}")
            return 0

    @staticmethod
    def calculate_weekly_aggregates(db: Session, user_id: int) -> Dict:
        """
        Calculate current week's training metrics
        """
        try:
            # Get this week's activities (Monday-Sunday)
            today = datetime.now(timezone.utc).date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)

            start_datetime = datetime.combine(start_of_week, datetime.min.time(), tzinfo=timezone.utc)
            end_datetime = datetime.combine(end_of_week, datetime.max.time(), tzinfo=timezone.utc)

            weekly_activities = (
                db.query(Activity)
                .filter(
                    Activity.user_id == user_id,
                    Activity.start_date_utc >= start_datetime,
                    Activity.start_date_utc <= end_datetime,
                )
                .all()
            )

            total_volume_km = sum(a.distance_km for a in weekly_activities)
            total_tss = sum(a.training_stress_score_tss for a in weekly_activities)
            avg_hr = (
                sum(a.avg_heart_rate for a in weekly_activities if a.avg_heart_rate) / len(weekly_activities)
                if weekly_activities and any(a.avg_heart_rate for a in weekly_activities)
                else 0
            )

            intensity_factor = total_tss / (sum(a.moving_time_min for a in weekly_activities) / 60) if weekly_activities else 0

            return {
                "volume_km": round(total_volume_km, 1),
                "tss": round(total_tss, 1),
                "avg_hr": round(avg_hr, 0) if avg_hr else 0,
                "intensity_factor": round(intensity_factor, 2),
                "workout_count": len(weekly_activities),
                "week_start": start_of_week.isoformat(),
                "week_end": end_of_week.isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Weekly aggregates error: {e}")
            return {}

    @staticmethod
    def calculate_readiness_score(ctl: float, atl: float, tsb: float) -> float:
        """
        Calculate athlete readiness score (0-100)
        Based on TSB: positive TSB = recovered, negative = fatigued
        """
        # TSB of +10 to +20 is optimal (fresh, recovered)
        # TSB of 0 is neutral
        # TSB of -20 to -40 is heavy fatigue
        # TSB < -40 is overtraining risk

        if tsb > 20:
            readiness = 100  # Fully recovered, maybe overtrained
        elif tsb > 10:
            readiness = 90  # Very fresh
        elif tsb > 0:
            readiness = 80  # Fresh, good for workouts
        elif tsb > -5:
            readiness = 70  # Neutral
        elif tsb > -20:
            readiness = 50  # Fatigued, recovery day recommended
        elif tsb > -40:
            readiness = 30  # Heavy fatigue, mandatory rest
        else:
            readiness = 10  # Severe fatigue, overtraining risk

        return float(readiness)

    @staticmethod
    def calculate_injury_risk_score(db: Session, user_id: int) -> float:
        """
        Calculate injury risk (0-100)
        Based on: acute:chronic workload ratio, rapid volume increases, insufficient recovery
        """
        try:
            ctl, atl, tsb = MetricsCalculator.calculate_ctl_atl_tsb(db, user_id)

            # Rule 1: Acute:Chronic workload ratio
            # Safe: 0.8-1.3, at-risk: >1.5
            acl_ratio = atl / ctl if ctl > 0 else 0
            if acl_ratio > 1.5:
                risk = 70  # High acute load relative to chronic
            elif acl_ratio > 1.3:
                risk = 50  # Moderate acute load
            else:
                risk = 20  # Safe zone

            # Rule 2: TSB too negative (heavy fatigue)
            if tsb < -40:
                risk = min(100, risk + 30)

            # Rule 3: Insufficient recovery days
            last_7_days = datetime.now(timezone.utc) - timedelta(days=7)
            workouts_last_week = (
                db.query(Activity)
                .filter(Activity.user_id == user_id, Activity.start_date_utc >= last_7_days)
                .count()
            )

            if workouts_last_week > 6:  # >1 workout per day on average
                risk = min(100, risk + 20)

            return float(risk)

        except Exception as e:
            logger.error(f"❌ Injury risk calculation error: {e}")
            return 25.0  # Default moderate risk


class MetricsPipeline:
    """
    Main pipeline to process all user metrics after activity sync
    """

    @staticmethod
    def process_user_metrics(db: Session, user_id: int) -> Dict:
        """
        Complete metrics calculation and update for a single user
        """
        try:
            logger.info(f"🔄 Processing metrics for user {user_id}")

            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"success": False, "error": "User not found"}

            # Calculate all metrics
            ctl, atl, tsb = MetricsCalculator.calculate_ctl_atl_tsb(db, user_id)
            vo2max = MetricsCalculator.estimate_vo2max(db, user_id)
            hr_zones = MetricsCalculator.calculate_hr_zones(user)
            personal_records = MetricsCalculator.calculate_personal_records(db, user_id)
            training_age = MetricsCalculator.analyze_training_age(db, user_id)
            weekly_agg = MetricsCalculator.calculate_weekly_aggregates(db, user_id)
            readiness = MetricsCalculator.calculate_readiness_score(ctl, atl, tsb)
            injury_risk = MetricsCalculator.calculate_injury_risk_score(db, user_id)

            # Update user profile
            user.atl = atl
            user.ctl = ctl
            user.tsb = tsb
            user.physiological_twin["vo2max_estimate"] = vo2max
            user.precomputed_snapshot = {
                "ctl": ctl,
                "atl": atl,
                "tsb": tsb,
                "vo2max": vo2max,
                "hr_zones": hr_zones,
                "readiness": readiness,
                "injury_risk": injury_risk,
                "training_age": training_age,
                "weekly": weekly_agg,
                "personal_records": personal_records,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            # Store weekly performance metric
            today = datetime.now(timezone.utc)
            existing_metric = (
                db.query(PerformanceMetric)
                .filter(
                    PerformanceMetric.user_id == user_id,
                    func.date(PerformanceMetric.metric_date) == today.date(),
                )
                .first()
            )

            if existing_metric:
                existing_metric.weekly_volume_km = weekly_agg.get("volume_km", 0)
                existing_metric.weekly_tss = weekly_agg.get("tss", 0)
                existing_metric.readiness_score = readiness
                existing_metric.injury_risk_score = injury_risk
            else:
                metric = PerformanceMetric(
                    user_id=user_id,
                    metric_date=today,
                    period_type="daily",
                    weekly_volume_km=weekly_agg.get("volume_km", 0),
                    weekly_tss=weekly_agg.get("tss", 0),
                    readiness_score=readiness,
                    injury_risk_score=injury_risk,
                )
                db.add(metric)

            db.commit()

            logger.info(
                f"✅ Metrics updated for user {user_id}: "
                f"CTL={ctl}, ATL={atl}, TSB={tsb}, VO2Max={vo2max}, Readiness={readiness}"
            )

            return {
                "success": True,
                "ctl": ctl,
                "atl": atl,
                "tsb": tsb,
                "vo2max": vo2max,
                "readiness": readiness,
                "injury_risk": injury_risk,
            }

        except Exception as e:
            logger.error(f"❌ Metrics pipeline error: {e}", exc_info=True)
            db.rollback()
            return {"success": False, "error": str(e)}
