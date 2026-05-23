# backend/athlete_state/adaptation_learning.py
import logging
from backend.models import User, Activity

logger = logging.getLogger(__name__)

class AdaptationLearning:
    """
    Adaptive State-Space learning engine. 
    Calibrates personalized recovery decay rates and fatigue sensitivity coefficients
    over time by analyzing workout responses.
    """

    @staticmethod
    def update_coefficients(db, user_id: int, latest_activity: Activity):
        """
        Updates the user's personalized recovery and fatigue coefficients.
        Uses a Kalman-style state-space filter: new_coefficient = old * (1 - alpha) + observed * alpha
        """
        user = db.query(User).filter_by(id=user_id).first()
        if not user or not latest_activity:
            return

        # Alpha determines the rate of learning (0.10 is stable, 0.30+ is aggressive)
        alpha = 0.10

        try:
            # 1. Update Personal Recovery Velocity
            # Compare perceived recovery speed against total cardiovascular stress (TSS)
            rpe = latest_activity.perceived_exertion_rpe or 5
            tss = latest_activity.training_stress_score_tss or 30.0

            # Estimate recovery speed: a high RPE for low TSS indicates a slower recovery velocity
            observed_recovery_velocity = 1.0
            if tss > 0:
                stress_effort_ratio = rpe / (tss / 10.0)
                if stress_effort_ratio > 1.5:
                    # Slow recovery velocity (higher perceived strain for the load)
                    observed_recovery_velocity = 0.82
                elif stress_effort_ratio < 0.8:
                    # Fast recovery velocity (efficient recovery and low perceived strain)
                    observed_recovery_velocity = 1.25

            # Apply state-space filter to smooth out sudden anomalies
            user.recovery_velocity = round((user.recovery_velocity * (1.0 - alpha)) + (observed_recovery_velocity * alpha), 3)

            # 2. Update Personal Fatigue Accumulation Rate (Sensitivity to spikes)
            # Checked by comparing cadence decay rates against the aerobic drift velocity
            drift = latest_activity.cardiac_decoupling or 0.0
            decay = latest_activity.cadence_degradation or 0.0

            observed_fatigue_accumulation_rate = 1.0
            if drift > 0.08 or decay > 0.05:
                # Structural fatigue spike detected; indicating high sensitivity to load
                observed_fatigue_accumulation_rate = 1.35
            elif drift < 0.02 and decay < 0.01:
                # High durability; indicating low sensitivity to load
                observed_fatigue_accumulation_rate = 0.80

            user.fatigue_accumulation_rate = round((user.fatigue_accumulation_rate * (1.0 - alpha)) + (observed_fatigue_accumulation_rate * alpha), 3)

            # 3. Update Heat Tolerance Index
            temp_c = latest_activity.temperature_c or 20.0
            if temp_c > 28.0 and latest_activity.avg_heart_rate:
                # Compare cardiac decoupling during hot workouts to baseline efficiency
                observed_heat_tolerance = 1.0
                if drift > 0.06:
                    # Low heat tolerance: heart rate spiked significantly in the heat
                    observed_heat_tolerance = 0.35
                elif drift < 0.03:
                    # High heat tolerance: cardiovascular efficiency remained stable
                    observed_heat_tolerance = 0.85
                
                user.heat_tolerance_index = round((user.heat_tolerance_index * (1.0 - alpha)) + (observed_heat_tolerance * alpha), 3)

            db.add(user)
            db.commit()
            logger.info(f"🧬 Athlete adaptation coefficients updated for User {user_id}: RecVelocity={user.recovery_velocity}, FatigueSensitivity={user.fatigue_accumulation_rate}")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Adaptation learning failed for user {user_id}: {str(e)}", exc_info=True)
