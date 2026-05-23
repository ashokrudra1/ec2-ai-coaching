# backend/athlete_state/recovery_biomarkers.py
import logging

logger = logging.getLogger(__name__)

class RecoveryBiomarkers:
    """
    Multi-Factor Recovery Biomarker Integration Engine.
    Combines subjective feedback and objective metrics (HRV, RHR, Sleep) to track fatigue.
    """

    @staticmethod
    def calculate_recovery_score(
        hrv_ms: float, 
        resting_hr: float, 
        sleep_hours: float, 
        soreness_score: int, 
        user_baseline_hrv: float = 60.0,
        user_baseline_rhr: float = 55.0
    ) -> dict:
        """
        Calculates an objective recovery score.
        Scores: 0.0 (Severe Exhaustion) to 100.0 (Fully Restored)
        """
        try:
            # 1. HRV Penalty/Bonus (HRV drop indicates autonomic nervous system strain)
            hrv_ratio = hrv_ms / user_baseline_hrv if user_baseline_hrv > 0 else 1.0
            hrv_score = 100.0 * hrv_ratio
            hrv_score = max(0.0, min(100.0, hrv_score))

            # 2. Resting HR Delta Penalty (Elevated RHR indicates physical stress)
            rhr_delta = resting_hr - user_baseline_rhr
            rhr_score = 100.0
            if rhr_delta > 0:
                rhr_score = max(30.0, 100.0 - (rhr_delta * 4.0))

            # 3. Sleep Volume Score
            sleep_score = 100.0
            if sleep_hours < 8.0:
                sleep_score = max(20.0, 100.0 - ((8.0 - sleep_hours) * 15.0))

            # 4. Soreness Penalty (1-10 Scale)
            soreness_score_bounded = max(1, min(10, soreness_score))
            soreness_score_calc = (10 - soreness_score_bounded) * 10.0

            # 5. Weighted Recovery Score Synthesis
            weighted_score = (
                (hrv_score * 0.35) + 
                (rhr_score * 0.25) + 
                (sleep_score * 0.20) + 
                (soreness_score_calc * 0.20)
            )
            final_score = round(max(10.0, min(100.0, weighted_score)), 1)

            # Determine subjective readiness classification
            if final_score >= 85.0:
                readiness_class = "Fully Restored (Ready for High Intensity)"
            elif final_score >= 65.0:
                readiness_class = "Baseline Stabilized (Aerobic Volume Permitted)"
            elif final_score >= 45.0:
                readiness_class = "Autonomic Strain (Recovery Focus Only)"
            else:
                readiness_class = "System Exhausted (Complete Rest Demanded)"

            return {
                "recovery_score": final_score,
                "readiness_classification": readiness_class,
                "biomarker_metrics": {
                    "hrv_retention": round(hrv_ratio * 100.0, 1),
                    "rhr_elevation": round(rhr_delta, 1),
                    "sleep_deficit_hours": round(max(0.0, 8.0 - sleep_hours), 1)
                }
            }

        except Exception as e:
            logger.error(f"❌ RecoveryBiomarkers calculation failed: {str(e)}")
            return {"recovery_score": 75.0, "readiness_classification": "Baseline Stabilized", "biomarker_metrics": {}}
