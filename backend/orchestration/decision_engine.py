# backend/orchestration/decision_engine.py
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanProposal:
    workout: str
    intensity_zone: int
    rationale: str
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class Objection:
    objection_id: str
    severity: str  # 'info' | 'warning' | 'critical'
    rationale: str
    metadata: Dict[str, Any]


class CouncilAgent(Protocol):
    agent_id: str

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]: ...


class TrainingPlannerAgent:
    agent_id = "TrainingPlannerAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        running_resp = TrainingPrescriptionEngine.prescribe_polarized_block(context)
        proposal = PlanProposal(
            workout=running_resp.get("recommended_workout", ""),
            intensity_zone=int(running_resp.get("target_intensity_zone") or 1),
            rationale=running_resp.get("rationale", ""),
            metadata={"source": "TrainingPrescriptionEngine"},
        )
        return proposal, []


class RecoveryAgent:
    agent_id = "RecoveryAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        objections: List[Objection] = []
        recovery_score = float(context.get("recovery_score", 100.0) or 100.0)
        if recovery_score < 45.0:
            objections.append(
                Objection(
                    objection_id="low_recovery_score",
                    severity="warning",
                    rationale="Recovery Score < 45 suggests autonomic strain; downgrade intensity.",
                    metadata={"recovery_score": recovery_score},
                )
            )
        return None, objections


class InjuryRiskAgent:
    agent_id = "InjuryRiskAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        objections: List[Objection] = []
        predictive_risk = context.get("predictive_risk", {}) or {}
        injury_p = float(predictive_risk.get("injury_probability_14d", 0.0) or 0.0)
        burnout_p = float(predictive_risk.get("burnout_probability_21d", 0.0) or 0.0)
        if injury_p > 0.65:
            objections.append(
                Objection(
                    objection_id="injury_probability_high",
                    severity="critical",
                    rationale="14-day injury probability exceeds 65% limit.",
                    metadata={"injury_probability_14d": injury_p},
                )
            )
        if burnout_p > 0.65:
            objections.append(
                Objection(
                    objection_id="burnout_probability_high",
                    severity="warning",
                    rationale="21-day burnout probability elevated; bias toward lower impact.",
                    metadata={"burnout_probability_21d": burnout_p},
                )
            )
        return None, objections


class FatigueGuardianAgent:
    agent_id = "FatigueGuardianAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        objections: List[Objection] = []
        tsb = float((context.get("fatigue_metrics", {}) or {}).get("tsb", 0.0) or 0.0)
        if tsb < -20.0:
            objections.append(
                Objection(
                    objection_id="fatigue_guardrail_tsb",
                    severity="critical",
                    rationale="TSB below -20 indicates high-risk fatigue state; block hard training.",
                    metadata={"tsb": tsb},
                )
            )
        elif tsb < -10.0:
            objections.append(
                Objection(
                    objection_id="fatigue_caution_tsb",
                    severity="warning",
                    rationale="TSB below -10 indicates elevated fatigue; avoid hard intensity.",
                    metadata={"tsb": tsb},
                )
            )
        return None, objections


class MotivationAgent:
    agent_id = "MotivationAgent"

    def propose(self, context: dict) -> Tuple[Optional[PlanProposal], List[Objection]]:
        # Phase-1 deterministic tone hints; CoachService can map this into persona/tone later.
        psych = context.get("psychological", {}) or {}
        burnout_risk = float(psych.get("burnout_risk", 0.0) or 0.0)
        confidence = float(psych.get("confidence", 0.8) or 0.8)
        style = "analytical"
        if burnout_risk > 0.5:
            style = "supportive"
        elif confidence < 0.5:
            style = "supportive"
        return (
            None,
            [
                Objection(
                    objection_id="tone_hint",
                    severity="info",
                    rationale=f"Recommended tone_style={style} based on psychological twin.",
                    metadata={"tone_style": style, "burnout_risk": burnout_risk, "confidence": confidence},
                )
            ],
        )


class CouncilCoordinator:
    def __init__(self, agents: List[CouncilAgent]):
        self._agents = agents

    def run(self, context: dict) -> Dict[str, Any]:
        proposals: List[Dict[str, Any]] = []
        objections: List[Dict[str, Any]] = []

        chosen: Optional[PlanProposal] = None
        for agent in self._agents:
            proposal, agent_objections = agent.propose(context)
            if proposal is not None and chosen is None:
                chosen = proposal
            if proposal is not None:
                proposals.append({"agent_id": agent.agent_id, **proposal.__dict__})
            for obj in agent_objections:
                objections.append({"agent_id": agent.agent_id, **obj.__dict__})

        if chosen is None:
            chosen = PlanProposal(
                workout="Recovery movement: walk or easy spin 20–30 minutes",
                intensity_zone=1,
                rationale="No planner proposal available; defaulting to conservative recovery.",
                metadata={"source": "CouncilCoordinator.default"},
            )

        return {"chosen": chosen, "proposals": proposals, "objections": objections}

class TrainingPrescriptionEngine:
    """
    Olympic Periodization & Workout Prescription Engine.
    Executes block periodization, polarized models, and fatigue-based workout swaps.
    """

    @staticmethod
    def prescribe_polarized_block(user_state: dict) -> dict:
        """
        Generates custom workout parameters based on physical load limits
        and historical training patterns.
        """
        phase = user_state.get("training_phase", "Base").lower()
        tsb = user_state.get("fatigue_metrics", {}).get("tsb", 0.0)
        goal = user_state.get("goal", "general").lower()
        
        # Calculate physiological heart rate boundaries
        zones = user_state.get("hr_zones", {"zone1": 115, "zone2": 133, "zone3": 152, "zone4": 171, "zone5": 190})

        prescription = {
            "recommended_workout": "Steady Aerobic Base Run - 45 mins",
            "target_intensity_zone": 2,
            "rationale": "Accumulating low-intensity aerobic volume to build mitochondrial capacity."
        }

        # 1. Base Building Phase (High-volume base runs)
        if phase == "base":
            prescription = {
                "recommended_workout": f"Steady Endurance Run (Zone 2: {zones['zone1']}-{zones['zone2']} bpm) - 60 mins",
                "target_intensity_zone": 2,
                "rationale": "Focus on capillary bed development and establishing active volume thresholds."
            }
        
        # 2. Build Phase (Speed Intervals / Lactate Threshold Blocks)
        elif phase == "build":
            if tsb >= -5.0:
                prescription = {
                    "recommended_workout": f"Lactate Threshold Intervals (3x 2km in Zone 4: {zones['zone3']}-{zones['zone4']} bpm, with 3 min walking recovery)",
                    "target_intensity_zone": 4,
                    "rationale": "Structured interval work designed to push anaerobic velocity and lactate tolerance."
                }
            else:
                # Fatigue-Aware Swap: Auto-downgrade target workout if form is poor
                prescription = {
                    "recommended_workout": f"Fatigue-Bypassed Recovery Run (Zone 1: Under {zones['zone1']} bpm) - 30 mins",
                    "target_intensity_zone": 1,
                    "rationale": "Form is low (TSB < -5). Speed session swapped for active recovery to prevent joint stress."
                }

        # 3. Peak Phase (Target marathon pacing simulation)
        elif phase == "peak":
            prescription = {
                "recommended_workout": f"Aerobic Threshold Tempo Session (Warmup -> 30 mins steady in Zone 3: {zones['zone2']}-{zones['zone3']} bpm -> Cooldown)",
                "target_intensity_zone": 3,
                "rationale": "Simulating marathon-pace energy demands and fuel efficiency targets."
            }

        # 4. Taper Phase (Exponential volume decay)
        elif phase == "taper":
            prescription = {
                "recommended_workout": f"Short Maintenance Stride Intervals (Zone 4: {zones['zone3']}-{zones['zone4']} bpm) - 25 mins",
                "target_intensity_zone": 4,
                "rationale": "Reduce volume while maintaining intensity to peak neuro-muscular freshness."
            }

        return prescription


class ConflictResolutionRouter:
    """Arbitrates specialist recommendations against predictive injury and burnout risks."""
    @staticmethod
    def arbitrate(running_decision: dict, recovery_score: float, predictive_risk: dict) -> dict:
        action = running_decision.get("recommended_workout")
        intensity = running_decision.get("target_intensity_zone")
        override_reason = None

        # Rule 1: High Predictive Injury Risk
        if predictive_risk.get("injury_probability_14d", 0.0) > 0.65:
            action = "Complete Active Recovery & Muscle Foam Rolling"
            intensity = 1
            override_reason = "14-day injury risk exceeds 65% safety limits. Active intervention applied."

        # Rule 2: Low Recovery Score / Autonomic Nervous System Strain
        elif recovery_score < 45.0:
            action = "Bypassed Training Rest Day - Focus on Sleep"
            intensity = 1
            override_reason = "Biomarkers indicate autonomic strain (Recovery Score < 45). Session cancelled."

        # Rule 3: Burnout Risk Override
        elif predictive_risk.get("burnout_probability_21d", 0.0) > 0.65:
            action = "Low-Impact Active Movement Walk - 30 mins"
            intensity = 1
            override_reason = "Cognitive burnout parameters are spiking. Training target set to low-impact."

        return {
            "final_action": action,
            "final_intensity_zone": intensity,
            "is_overridden": override_reason is not None,
            "override_reason": override_reason
        }


class DecisionEngine:
    @staticmethod
    def generate_final_response(context: dict) -> dict:
        """Coordinates and arbitrates programmatic coaching decisions (deterministic council)."""
        council = CouncilCoordinator(
            agents=[
                TrainingPlannerAgent(),
                FatigueGuardianAgent(),
                InjuryRiskAgent(),
                RecoveryAgent(),
                MotivationAgent(),
            ]
        )
        council_result = council.run(context)
        chosen: PlanProposal = council_result["chosen"]

        running_resp = {
            "recommended_workout": chosen.workout,
            "target_intensity_zone": chosen.intensity_zone,
            "rationale": chosen.rationale,
        }

        arbitration = ConflictResolutionRouter.arbitrate(
            running_decision=running_resp,
            recovery_score=context.get("recovery_score", 100.0),
            predictive_risk=context.get("predictive_risk", {}),
        )

        return {
            "arbitrated_plan": arbitration,
            "running_analysis": running_resp,
            "council": {
                "proposals": council_result["proposals"],
                "objections": council_result["objections"],
            },
        }
