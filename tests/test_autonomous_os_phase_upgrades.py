from backend.orchestration.autonomous_planner import AutonomousPlanner
from backend.sports_science.adaptation_forecaster import AdaptationForecaster


class DummyUser:
    def __init__(self, tsb, twin):
        self.tsb = tsb
        self.physiological_twin = twin


def test_adaptation_forecaster_outputs_bounded_probabilities():
    forecast = AdaptationForecaster.forecast(
        tsb=-8.0,
        acwr=1.22,
        recovery_index=58.0,
        cardiac_decoupling=0.06,
    )
    for value in (
        forecast.adaptation_probability_7d,
        forecast.fatigue_risk_7d,
        forecast.injury_probability_14d,
        forecast.burnout_probability_21d,
        forecast.readiness_next_72h,
    ):
        assert 0.0 <= value <= 1.0


def test_autonomous_planner_recovery_focus_trigger():
    user = DummyUser(
        tsb=-12.0,
        twin={"adaptation_forecast": {"readiness_next_72h": 0.40, "injury_probability_14d": 0.2}},
    )
    plan = AutonomousPlanner.build_checkin_plan(user)
    assert plan.should_send is True
    assert plan.reason in {"recovery_focus", "injury_risk_high"}


def test_autonomous_planner_live_intervention_hint():
    hint = AutonomousPlanner.intervention_hint_from_activity(
        {"average_heartrate": 186, "distance": 10000, "moving_time": 3500},
        tsb=-4.0,
    )
    assert hint is not None
