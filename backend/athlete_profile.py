import logging
from datetime import datetime

from backend.models import User
from backend.analytics import (
    get_fatigue_metrics,
    get_performance_summary,
    get_recent_form,
    get_personal_bests
)

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
            today = datetime.utcnow().date()
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
    # 📈 PERFORMANCE
    # =========================
    performance = get_performance_summary(db, user_id)
    recent_form = get_recent_form(db, user_id)
    personal_bests = get_personal_bests(db, user_id)

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
