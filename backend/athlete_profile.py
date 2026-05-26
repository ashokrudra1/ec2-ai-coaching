import logging
from datetime import datetime, timezone

from backend.models import User
from backend.analytics import get_fatigue_metrics
from backend.training_system.metrics_calculator import MetricsCalculator

logger = logging.getLogger(__name__)

# =========================
# 👤 GET ATHLETE CONTEXT
# =========================
def get_athlete_context(db, user_id):
    """
    Returns a structured athlete profile used by coach_engine
    """
    user = db.query(User).filter_by(id=user_id).first()

    if not user:
        return {
            "name": "Athlete",
            "profile": "No data available",
            "fatigue": {},
            "performance": {},
            "recent_form": {},
            "personal_bests": {}
        }

    # =========================
    # 🎂 AGE CALCULATION
    # =========================
    age = None
    if user.dob:
        try:
            today = datetime.now(timezone.utc).date()
            age = (
                today.year - user.dob.year
                - ((today.month, today.day) < (user.dob.month, user.dob.day))
            )
        except Exception:
            age = None

    # =========================
    # 📊 METRICS
    # =========================
    atl, ctl, tsb, fatigue_status = get_fatigue_metrics(db, user_id)

    # =========================
    # 📈 PERFORMANCE & PRs
    # =========================
    # Using the standardized MetricsCalculator
    performance = MetricsCalculator.calculate_weekly_aggregates(db, user_id)
    personal_bests = MetricsCalculator.calculate_personal_records(db, user_id)
    
    # Recent form can be derived from TSB and recent aggregates
    recent_form = {
        "tsb": tsb,
        "status": fatigue_status,
        "volume_last_7_days": performance.get("volume_km", 0)
    }

    # =========================
    # 🧠 PROFILE SUMMARY
    # =========================
    profile_text = (
        f"Name: {user.name}\n"
        f"Age: {age if age else 'N/A'}\n"
        f"Goal: {user.target_goal or 'Not defined'}\n"
        f"Background: {user.background_bio or 'Not provided'}"
    )

    # =========================
    # 📦 FINAL CONTEXT
    # =========================
    return {
        "name": user.name or "Athlete",
        "profile": profile_text,
        "fatigue": {
            "atl": atl,
            "ctl": ctl,
            "tsb": tsb,
            "status": fatigue_status
        },
        "performance": performance,
        "recent_form": recent_form,
        "personal_bests": personal_bests
    }
