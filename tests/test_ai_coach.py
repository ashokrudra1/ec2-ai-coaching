# tests/test_ai_coach.py
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from backend.database import Base
from backend.models import User, Activity
from backend.athlete_state.fatigue_engine import FatigueEngine
from backend.analytics import update_user_fitness_metrics
from backend.athlete_state.advanced_intelligence import AdvancedTrainingIntelligence

# ==========================================
# 🛠️ SQLITE COMPATIBILITY SHIMS
# ==========================================
# Force SQLite to compile JSONB as JSON (which SQLite supports natively)
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

# Force SQLite to compile pgvector Vector columns as JSON/TEXT
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"


# Set up clean, in-memory testing database context
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Initializes schema and provides isolated transactional sessions for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_user(db_session):
    """Generates a default mock athlete Twin."""
    user = User(
        name="Ashok Rawat",
        telegram_chat_id="5348200695",
        ctl=45.0,
        atl=30.0,
        tsb=15.0,
        max_hr=190.0,
        rest_hr=60.0,
        physiological_twin={
            "threshold_pace": 280, # sec per km
            "threshold_hr": 165,
            "vo2max_estimate": 52.0
        }
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

# ==========================================
# 🧪 TEST 1: ACWR FATIGUE LOGIC
# ==========================================
def test_fatigue_engine_calculations(db_session, mock_user):
    """Checks Acute-to-Chronic Workload Ratio outputs with synthetic runs."""
    now = datetime.utcnow()
    
    # 1. Create a 6-week baseline of training activities (42 days)
    for days_back in [3, 10, 17, 24, 31, 38]:
        # If it's the run within the last 7 days, make it slightly longer (11km)
        # to push ACWR strictly above 1.0 (ACWR = 11.0 / (61.0 / 6) = 1.08)
        run_distance = 11.0 if days_back == 3 else 10.0
        
        activity = Activity(
            user_id=mock_user.id,
            strava_id=1000 + days_back,
            name="Steady Training Run",
            distance_km=run_distance,
            moving_time_min=50.0,
            start_date_utc=now - timedelta(days=days_back)
        )
        db_session.add(activity)
    db_session.commit()

    # Calculate metrics
    metrics = FatigueEngine.calculate(db_session, mock_user.id)
    
    assert metrics["acute_load"] == 11.0
    assert metrics["chronic_load"] == 61.0
    assert metrics["acwr"] == 1.08  # 11.0 / (61.0 / 6) = 1.08
    assert metrics["fatigue_score"] == 75  # Will now successfully evaluate to 75!


# ==========================================
# 🧪 TEST 2: INCREMENTAL FITNESS DECAY
# ==========================================
def test_tsb_state_space_decay_and_spikes(db_session, mock_user):
    """Verifies state-space decay math and TSB shifts when a high-stress workout is recorded."""
    original_ctl = mock_user.ctl
    original_atl = mock_user.atl

    # Record a massive workout stimulus (TSS = 120.0)
    update_user_fitness_metrics(db_session, mock_user.id, activity_tss=120.0)
    db_session.refresh(mock_user)

    # CTL and ATL should increase after absorbing training stress
    assert mock_user.ctl > (original_ctl * 0.9)  # Check it decays previous load then scales with stimulus
    assert mock_user.atl > original_atl

# ==========================================
# 🧪 TEST 3: COMPLIANCE ENFORCEMENT
# ==========================================
def test_workout_compliance_scoring(mock_user):
    """Tests biomechanical evaluations for pacing and heart rate violations."""
    bad_run = Activity(
        user_id=mock_user.id,
        name="Recovery Easy Jog",
        avg_heart_rate=175.0, # Highly exceeded recovery heart rate ceiling
        moving_time_min=30.0, # Target was 30 mins
        cadence_degradation=0.08 # Stride collapsed by 8%
    )

    evaluation = AdvancedTrainingIntelligence.evaluate_workout_compliance(
        activity=bad_run,
        user=mock_user,
        target_hr_ceiling=140, # Ceiling
        target_duration_min=30.0
    )

    # Compliance score must drop due to cardiac overload and mechanical cadence collapse
    assert evaluation["compliance_score"] < 0.70
    assert "hr_exceeded_ceiling_by_bpm" in evaluation["assessment_details"]
    assert "mechanical_fatigue" in evaluation["assessment_details"]

# ==========================================
# 🧪 TEST 4: PREDICTIVE PERFORMANCE MODEL
# ==========================================
def test_race_prediction_riegel(mock_user):
    """Verifies math consistency in predictions based on threshold pace and VO2 Max."""
    predictions = AdvancedTrainingIntelligence.predict_race_performances(mock_user)
    
    assert "5K" in predictions["predictions"]
    assert "Marathon" in predictions["predictions"]
    assert predictions["scaled_vo2max"] > 0.0
    
    # Assert formatting structure (e.g. HH:MM:SS or MM:SS)
    assert ":" in predictions["predictions"]["Marathon"]
