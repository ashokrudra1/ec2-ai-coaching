# backend/athlete_state/recovery_engine.py
class RecoveryEngine:

    @staticmethod
    def calculate(fatigue_score):
        if fatigue_score < 40:
            return 45  # Needs serious rest
        if fatigue_score < 60:
            return 65  # Light recovery active
        if fatigue_score < 80:
            return 80  # Good to go
        return 92  # Fully restored
