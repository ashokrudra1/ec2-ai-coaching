# backend/athlete_state/fatigue_engine.py
from datetime import datetime, timedelta
from backend.models import Activity

class FatigueEngine:

    @staticmethod
    def calculate(db, user_id):
        now = datetime.utcnow()
        acute_start = now - timedelta(days=7)
        chronic_start = now - timedelta(days=42)

        acute = (
            db.query(Activity)
            .filter(
                Activity.user_id == user_id,
                Activity.start_date_utc >= acute_start  # ✅ Fixed: Changed start_date_ist to start_date_utc
            )
            .all()
        )

        chronic = (
            db.query(Activity)
            .filter(
                Activity.user_id == user_id,
                Activity.start_date_utc >= chronic_start  # ✅ Fixed: Changed start_date_ist to start_date_utc
            )
            .all()
        )

        acute_load = sum(a.distance_km or 0 for a in acute)
        chronic_load = sum(a.distance_km or 0 for a in chronic)

        acwr = 0.0
        if chronic_load > 0:
            # ACWR = 7-day average load divided by 42-day average weekly load
            acwr = acute_load / (chronic_load / 6)

        # Baseline fatigue score (Higher is fresher, lower is more fatigued)
        fatigue_score = 100
        if acwr > 1.5:
            fatigue_score = 40  # Danger zone
        elif acwr > 1.2:
            fatigue_score = 60  # Productive stress
        elif acwr > 1.0:
            fatigue_score = 75  # Building fitness

        return {
            "acute_load": round(acute_load, 1),
            "chronic_load": round(chronic_load, 1),
            "acwr": round(acwr, 2),
            "fatigue_score": fatigue_score
        }
