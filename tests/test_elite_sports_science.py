from datetime import datetime, timezone
from types import SimpleNamespace

from backend.sports_science.compliance import WorkoutComplianceEngine
from backend.sports_science.state_space import StateSpaceDecayModel, TrainingStressEvent


def test_state_space_decay_outputs_ctl_atl_tsb():
    events = [
        TrainingStressEvent(datetime(2026, 1, 1, tzinfo=timezone.utc), 80.0),
        TrainingStressEvent(datetime(2026, 1, 2, tzinfo=timezone.utc), 90.0),
        TrainingStressEvent(datetime(2026, 1, 3, tzinfo=timezone.utc), 0.0),
    ]

    state = StateSpaceDecayModel.from_events(events)

    assert state.ctl >= 0
    assert state.atl >= 0
    assert state.tsb == round(state.ctl - state.atl, 2)
    assert state.acwr >= 0


def test_critical_tsb_marks_high_injury_risk():
    state = StateSpaceDecayModel.describe(ctl=30.0, atl=55.0)

    assert state.tsb == -25.0
    assert state.fatigue_level == "critical"
    assert state.injury_risk_score >= 0.70


def test_workout_compliance_scores_prescribed_targets():
    activity = SimpleNamespace(
        distance_km=10.0,
        moving_time_min=50.0,
        avg_heart_rate=145.0,
        prescribed_workout={
            "target_pace_sec_per_km": 300,
            "target_hr_min": 140,
            "target_hr_max": 150,
            "target_duration_min": 50,
        },
        splits=[],
        perceived_exertion_rpe=None,
    )

    result = WorkoutComplianceEngine.evaluate_activity(activity)

    assert result.overall_score > 0.95
    assert result.pace_score == 1.0
    assert result.hr_score == 1.0


def test_cardiac_decoupling_detects_efficiency_drop():
    splits = [
        {"distance": 1000, "elapsed_time": 300, "average_heartrate": 140},
        {"distance": 1000, "elapsed_time": 300, "average_heartrate": 140},
        {"distance": 1000, "elapsed_time": 330, "average_heartrate": 150},
        {"distance": 1000, "elapsed_time": 330, "average_heartrate": 150},
    ]

    decoupling = WorkoutComplianceEngine.compute_cardiac_decoupling(splits)

    assert decoupling > 0.0
