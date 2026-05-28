from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from backend.orchestration.decision_engine import (
    CouncilAgent,
    CouncilCoordinator,
    FatigueGuardianAgent,
    InjuryRiskAgent,
    MotivationAgent,
    Objection,
    PlanProposal,
    RecoveryAgent,
    TrainingPlannerAgent,
)


class NutritionCoachAgent(CouncilAgent):
    agent_id = "NutritionCoachAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        recovery_score = float(context.get("recovery_score", 100.0) or 100.0)
        if recovery_score < 55.0:
            return None, [
                Objection(
                    objection_id="fueling_recovery_priority",
                    severity="warning",
                    rationale="Recovery score is suppressed; prioritize carbohydrate + hydration recovery block.",
                    metadata={"nutrition_protocol": "post_session_refuel"},
                )
            ]
        return None, []


class RaceStrategistAgent(CouncilAgent):
    agent_id = "RaceStrategistAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        phase = str(context.get("training_phase", "base")).lower()
        if phase in {"peak", "taper"}:
            return None, [
                Objection(
                    objection_id="race_specificity_hint",
                    severity="info",
                    rationale="Athlete is in race-focused phase; keep pacing specificity high and volume controlled.",
                    metadata={"race_focus": True},
                )
            ]
        return None, []


class SportsPsychologistAgent(CouncilAgent):
    agent_id = "SportsPsychologistAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        psych = context.get("psychological", {}) or {}
        anxiety = float(psych.get("anxiety", 0.0) or 0.0)
        frustration = float(psych.get("frustration_index", 0.0) or 0.0)
        if anxiety > 0.55 or frustration > 0.45:
            return None, [
                Objection(
                    objection_id="psychological_load_high",
                    severity="warning",
                    rationale="Psychological strain is elevated; simplify plan and use supportive coaching tone.",
                    metadata={"recommended_tone": "supportive"},
                )
            ]
        return None, []


def build_default_council() -> CouncilCoordinator:
    return CouncilCoordinator(
        agents=[
            TrainingPlannerAgent(),        # Physiologist/Training strategist
            RecoveryAgent(),               # Recovery coach
            NutritionCoachAgent(),         # Fueling strategy
            SportsPsychologistAgent(),     # Psychological adaptation
            RaceStrategistAgent(),         # Race pacing strategy
            InjuryRiskAgent(),             # Injury prevention specialist
            FatigueGuardianAgent(),        # Safety guardian
            MotivationAgent(),             # Sports psych tone advisor
        ]
    )


def run_coach_council(context: Dict) -> Dict[str, List[Dict]]:
    return build_default_council().run(context)
