import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SafetyRuleOutcome:
    rule_id: str
    description: str
    severity: str
    rationale: str
    source_metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SafetyDecision:
    """Deterministic decision object that encodes global coaching safety state."""

    # Whether the athlete is allowed to perform hard / intense training today.
    allow_hard_training: bool = True
    # Whether all AI-driven coaching should be blocked (e.g. emergency, red-line medical).
    block_coaching: bool = False
    # Recommended maximum intensity zone (1–5). Even when allow_hard_training=True,
    # this can constrain the prescription engine.
    max_intensity_zone: int = 5
    # Human-readable message to surface when safety state restricts training.
    safety_message: Optional[str] = None
    # List of rule outcomes that fired during evaluation.
    rules_fired: List[SafetyRuleOutcome] = field(default_factory=list)

    def register_rule(self, outcome: Optional[SafetyRuleOutcome]) -> None:
        if outcome is not None:
            self.rules_fired.append(outcome)


@dataclass
class SafetyContext:
    """Aggregated context for deterministic safety evaluation.

    This intentionally mirrors information already available in other layers
    (fatigue metrics, predictive risk, readiness, medical flags, etc.) but
    centralises policy decisions in one place.
    """

    user_id: Optional[int] = None

    # Fatigue / load model
    tsb: float = 0.0
    ctl: float = 0.0
    atl: float = 0.0
    acwr: Optional[float] = None

    # Predictive risk scores (0–1 probabilities)
    injury_probability_14d: float = 0.0
    burnout_probability_21d: float = 0.0

    # Recovery / readiness composite (0–100)
    recovery_score: float = 100.0

    # Medical / contraindication flags
    has_high_risk_medical_flags: bool = False

    # Psychological / behavioural state
    burnout_flag: bool = False
    adherence_issues: bool = False

    # Emergency detection from front-end channels
    emergency_triggered: bool = False

    # Arbitrary extra fields for future engines
    extras: Dict[str, Any] = dataclasses.field(default_factory=dict)


class FatigueSafetyEvaluator:
    """Evaluates chronic/acute load based safety rules."""

    # Mirrors AthleteMonitoringService.TSB_CRITICAL but lives centrally.
    TSB_CRITICAL = -20.0
    TSB_CAUTION = -10.0

    @classmethod
    def evaluate(cls, ctx: SafetyContext) -> Optional[SafetyRuleOutcome]:
        if ctx.tsb <= cls.TSB_CRITICAL:
            return SafetyRuleOutcome(
                rule_id="fatigue_critical_tsb",
                description="TSB below critical guardrail threshold.",
                severity="critical",
                rationale=f"TSB={ctx.tsb:.1f} is below {cls.TSB_CRITICAL}. Hard training is blocked.",
                source_metrics={"tsb": ctx.tsb},
            )
        if ctx.tsb <= cls.TSB_CAUTION:
            return SafetyRuleOutcome(
                rule_id="fatigue_caution_tsb",
                description="TSB in caution zone; restrict to endurance / low intensity.",
                severity="warning",
                rationale=f"TSB={ctx.tsb:.1f} is below {cls.TSB_CAUTION}. Prefer Zone 1–2 work.",
                source_metrics={"tsb": ctx.tsb},
            )
        return None


class InjuryRiskEvaluator:
    """Evaluates injury / burnout probabilities from predictive models."""

    INJURY_HARD_BLOCK = 0.65
    BURNOUT_CAUTION = 0.65

    @classmethod
    def evaluate(cls, ctx: SafetyContext) -> List[SafetyRuleOutcome]:
        outcomes: List[SafetyRuleOutcome] = []
        if ctx.injury_probability_14d > cls.INJURY_HARD_BLOCK:
            outcomes.append(
                SafetyRuleOutcome(
                    rule_id="injury_high_probability",
                    description="14-day injury risk exceeds hard safety limit.",
                    severity="critical",
                    rationale="Injury probability is above configured hard limit; enforce active recovery.",
                    source_metrics={"injury_probability_14d": ctx.injury_probability_14d},
                )
            )
        if ctx.burnout_probability_21d > cls.BURNOUT_CAUTION:
            outcomes.append(
                SafetyRuleOutcome(
                    rule_id="burnout_elevated_risk",
                    description="Burnout probability is elevated.",
                    severity="warning",
                    rationale="Burnout probability is elevated; bias towards low-impact work and recovery.",
                    source_metrics={"burnout_probability_21d": ctx.burnout_probability_21d},
                )
            )
        return outcomes


class MedicalSafetyEvaluator:
    """Evaluates medical boundaries derived from PDF analysis and clinician guidance."""

    @classmethod
    def evaluate(cls, ctx: SafetyContext) -> Optional[SafetyRuleOutcome]:
        if not ctx.has_high_risk_medical_flags:
            return None
        return SafetyRuleOutcome(
            rule_id="medical_high_risk",
            description="High-risk medical boundaries active.",
            severity="critical",
            rationale="Medical report indicates high-risk status; avoid high-intensity training and large volume spikes.",
            source_metrics={},
        )


class PsychologicalSafetyEvaluator:
    """Evaluates psychological state and adherence for safety-related downgrades."""

    @classmethod
    def evaluate(cls, ctx: SafetyContext) -> Optional[SafetyRuleOutcome]:
        if ctx.burnout_flag or ctx.adherence_issues:
            return SafetyRuleOutcome(
                rule_id="psychological_strain",
                description="Signs of psychological strain or adherence issues.",
                severity="warning",
                rationale="Recent communication and adherence metrics suggest strain; recommend lower intensity and simpler prescriptions.",
                source_metrics={
                    "burnout_flag": ctx.burnout_flag,
                    "adherence_issues": ctx.adherence_issues,
                },
            )
        return None


class EmergencyEvaluator:
    """Evaluates acute emergency triggers that must hard-stop coaching."""

    @classmethod
    def evaluate(cls, ctx: SafetyContext) -> Optional[SafetyRuleOutcome]:
        if not ctx.emergency_triggered:
            return None
        return SafetyRuleOutcome(
            rule_id="emergency_symptoms_reported",
            description="Athlete has reported acute emergency symptoms.",
            severity="critical",
            rationale="Emergency phrases detected in athlete communication; all coaching is suspended and athlete must contact emergency services.",
            source_metrics={},
        )


class PolicyEngine:
    """Centralised deterministic safety engine for coaching decisions."""

    @classmethod
    def evaluate(cls, context: SafetyContext) -> SafetyDecision:
        decision = SafetyDecision()

        # Priority 1: Immediate emergencies – block all coaching.
        emergency_outcome = EmergencyEvaluator.evaluate(context)
        if emergency_outcome:
            decision.block_coaching = True
            decision.allow_hard_training = False
            decision.max_intensity_zone = 1
            decision.safety_message = (
                "CRITICAL SAFETY: symptoms suggest possible medical emergency. "
                "Stop training and seek urgent medical care."
            )
            decision.register_rule(emergency_outcome)
            return decision

        # Priority 2: High-risk medical boundaries.
        medical_outcome = MedicalSafetyEvaluator.evaluate(context)
        if medical_outcome:
            decision.allow_hard_training = False
            decision.max_intensity_zone = 2
            decision.safety_message = (
                "Medical boundaries indicate you should avoid high-intensity work. "
                "Sticking to low-intensity endurance and movement is recommended."
            )
            decision.register_rule(medical_outcome)

        # Priority 3: Injury / burnout probabilities.
        for risk_outcome in InjuryRiskEvaluator.evaluate(context):
            decision.register_rule(risk_outcome)
            if risk_outcome.rule_id == "injury_high_probability":
                decision.allow_hard_training = False
                decision.max_intensity_zone = 1
                decision.safety_message = (
                    "Injury risk is elevated; switching to active recovery and removing intense work."
                )

        # Priority 4: Fatigue load (TSB/ACWR).
        fatigue_outcome = FatigueSafetyEvaluator.evaluate(context)
        if fatigue_outcome:
            decision.register_rule(fatigue_outcome)
            if fatigue_outcome.rule_id == "fatigue_critical_tsb":
                decision.allow_hard_training = False
                decision.max_intensity_zone = 1
                if not decision.safety_message:
                    decision.safety_message = (
                        "Form score is deeply negative; enforcing recovery-focused coaching until you rebound."
                    )
            elif fatigue_outcome.rule_id == "fatigue_caution_tsb":
                decision.max_intensity_zone = min(decision.max_intensity_zone, 2)

        # Priority 5: Psychological strain.
        psychological_outcome = PsychologicalSafetyEvaluator.evaluate(context)
        if psychological_outcome:
            decision.register_rule(psychological_outcome)
            decision.max_intensity_zone = min(decision.max_intensity_zone, 3)

        return decision

