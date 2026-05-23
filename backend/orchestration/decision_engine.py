# backend/orchestration/decision_engine.py
import logging

logger = logging.getLogger(__name__)

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
        """Coordinates and arbitrates programmatic coaching decisions."""
        running_resp = TrainingPrescriptionEngine.prescribe_polarized_block(context)
        
        arbitration = ConflictResolutionRouter.arbitrate(
            running_decision=running_resp,
            recovery_score=context.get("recovery_score", 100.0),
            predictive_risk=context.get("predictive_risk", {})
        )

        return {
            "arbitrated_plan": arbitration,
            "running_analysis": running_resp
        }
