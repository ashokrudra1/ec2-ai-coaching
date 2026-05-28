from backend.athlete_state.digital_twin_engine import DigitalTwinEngine
from backend.live_coaching.intervention_engine import LiveCoachingInterventionEngine, LiveSignal
from backend.recovery.recovery_optimizer import RecoveryOptimizer


def test_recovery_optimizer_generates_protocol():
    state = RecoveryOptimizer.compute_recovery_state(
        hrv_baseline=62.0,
        hrv_today=50.0,
        sleep_hours=5.8,
        load_tss_24h=170.0,
        resting_hr_delta=6.0,
    )
    protocol = RecoveryOptimizer.daily_recovery_protocol(state)
    assert state["readiness_score"] < 100.0
    assert len(protocol) > 0


def test_digital_twin_engine_projection_bounds():
    projection = DigitalTwinEngine.simulate(
        {
            "fatigue_metrics": {"tsb": -12.0, "acwr": 1.35, "ctl": 45.0, "tss_24h": 140.0},
            "physiological": {"structural_decay_rate": 0.05, "aerobic_drift_velocity": 0.06, "carb_quality_score": 0.55},
            "behavioral": {"compliance_rate": 0.78},
            "psychological": {"burnout_risk": 0.45, "frustration_index": 0.3, "adherence_velocity": 0.75},
        }
    )
    assert 0.0 <= projection.readiness_24h <= 1.0
    assert 0.0 <= projection.injury_trajectory_14d <= 1.0
    assert projection.glycogen_state in {"replenished", "partial", "depleted"}


def test_live_coaching_interventions_trigger():
    interventions = LiveCoachingInterventionEngine.evaluate(
        LiveSignal(
            avg_hr=187.0,
            hr_threshold=178.0,
            pace_sec_per_km=410.0,
            target_pace_sec_per_km=360.0,
            cardiac_drift=8.2,
            heat_index_c=35.0,
        )
    )
    assert len(interventions) >= 3
