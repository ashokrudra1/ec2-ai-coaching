# backend/athlete_state/injury_risk_engine.py
class InjuryRiskEngine:

    @staticmethod
    def evaluate(acwr, fatigue_score):
        if acwr > 1.5:
            return "High"  # Training spikes are highly correlated with soft-tissue injury
        if fatigue_score < 50:
            return "Moderate"
        return "Low"
