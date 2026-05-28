# backend/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, BigInteger, Text, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    telegram_chat_id = Column(String, unique=True, index=True)

    org_id = Column(String(50), nullable=True, index=True)   # SaaS Tenant Separation
    coach_id = Column(String(50), nullable=True, index=True) # Human Coach RBAC Map
    role = Column(String(20), default="athlete")             # 'athlete' | 'coach' | 'admin'
    hashed_password = Column(String(255), nullable=True)     # For dashboard API access

    # Subscription & Payment
    subscription_plan = Column(String(50), nullable=True)    # 'Basic', 'Premium', 'Elite'
    subscription_expiry = Column(DateTime, nullable=True)
    payment_status = Column(String(20), default="pending")   # 'pending', 'active', 'expired', 'cancelled'

    # Training Stress Metrics (CTL/ATL/TSB)
    atl = Column(Float, default=0.0)   # Acute Training Load (7-day decay)
    ctl = Column(Float, default=0.0)   # Chronic Training Load (42-day decay)
    tsb = Column(Float, default=0.0)   # Training Stress Balance
    ctl_time_constant_days = Column(Float, default=42.0)
    atl_time_constant_days = Column(Float, default=7.0)
    fitness_state_updated_at = Column(DateTime, nullable=True)
    last_training_stress_date = Column(DateTime, nullable=True)

    # Longitudinal Coefficients
    recovery_velocity = Column(Float, default=1.0)
    fatigue_accumulation_rate = Column(Float, default=1.0)
    aerobic_adaptation_rate = Column(Float, default=1.0)
    heat_tolerance_index = Column(Float, default=0.5)

    # Periodization Configs
    training_phase = Column(String(30), default="Base") # 'Base', 'Build', 'Peak', 'Taper'
    macrocycle_week = Column(Integer, default=1)
    target_weekly_tss = Column(Float, default=150.0)

    # Profile & Settings
    email = Column(String, nullable=True, index=True)
    dob = Column(DateTime, nullable=True)
    background_bio = Column(String, nullable=True)
    target_goal = Column(String, nullable=True)
    onboarding_step = Column(Integer, default=0)
    coach_persona = Column(String(20), default="veda")
    timezone = Column(String(50), nullable=True, default="UTC")
    age = Column(Integer, nullable=True)
    experience_level = Column(String(30), nullable=True)  # 'Beginner', 'Intermediate', 'Advanced', 'Elite'
    is_active = Column(Boolean, default=True)

    # Dynamic Twins (JSONB Snapshots)
    psychological_twin = Column(JSONB, default={
        "confidence": 0.8, "anxiety": 0.2, "motivation": 0.8,
        "burnout_risk": 0.05, "adherence_velocity": 1.0, "frustration_index": 0.1
    })
    behavioral_twin = Column(JSONB, default={
        "compliance_rate": 1.0, "skips_easy_runs": False,
        "runs_easy_too_hard": False, "pacing_discipline": 0.9
    })
    physiological_twin = Column(JSONB, default={
        "threshold_pace": 300, "threshold_hr": 165, "vo2max_estimate": 48.0,
        "aerobic_drift_velocity": 0.0, "structural_decay_rate": 0.0
    })

    # Cache Layer
    precomputed_snapshot = Column(JSONB, nullable=True)

    # Coaching States
    coaching_state = Column(String(30), default="Active Base")

    # Strava Metadata
    strava_athlete_id = Column(String, nullable=True)
    strava_custom_client_id = Column(String, nullable=True, index=True)
    strava_custom_client_secret_encrypted = Column(String, nullable=True)
    is_using_byok = Column(Boolean, default=False, nullable=False)
    max_hr = Column(Float, default=190.0)
    rest_hr = Column(Float, default=60.0)
    medical_insights = Column(Text, nullable=True)

    # Cost governance / usage metering
    monthly_token_quota = Column(Integer, nullable=True, default=500000)
    monthly_tokens_used = Column(Integer, nullable=True, default=0)

    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("CoachMemory", back_populates="user", cascade="all, delete-orphan")
    insights = relationship("AthleteInsight", back_populates="user", cascade="all, delete-orphan")
    medical_reports = relationship("MedicalReport", back_populates="user", cascade="all, delete-orphan")
    performance_metrics = relationship("PerformanceMetric", back_populates="user", cascade="all, delete-orphan")


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    strava_id = Column(BigInteger, unique=True, index=True)

    name = Column(String)
    type = Column(String)

    # Kinematics
    distance_km = Column(Float)
    moving_time_min = Column(Float)
    elapsed_time_min = Column(Float, nullable=True)
    start_date_utc = Column(DateTime, nullable=False)

    # Physiological Telemetry
    avg_heart_rate = Column(Float, nullable=True)
    max_heart_rate = Column(Float, nullable=True)
    avg_cadence = Column(Float, default=170.0)
    total_elevation_gain = Column(Float, default=0.0)
    splits = Column(JSONB, default=[])

    # Environmental Metrics
    temperature_c = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    elevation_m = Column(Float, nullable=True)
    weather_condition = Column(String(50), nullable=True)

    # Perceived Strain
    perceived_exertion_rpe = Column(Integer, nullable=True)
    training_stress_score_tss = Column(Float, default=0.0)

    # Sports Science Calculations
    cardiac_decoupling = Column(Float, default=0.0)
    cadence_degradation = Column(Float, default=0.0)
    glycogen_depleted_g = Column(Float, default=0.0)
    elevation_adjusted_tss = Column(Float, default=0.0)
    prescribed_workout = Column(JSONB, default={})
    compliance_score = Column(Float, nullable=True)
    pace_compliance_score = Column(Float, nullable=True)
    hr_compliance_score = Column(Float, nullable=True)
    compliance_breakdown = Column(JSONB, default={})

    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="activities")


class CoachMemory(Base):
    __tablename__ = "coach_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(String(20)) # 'user', 'assistant', 'system'
    content = Column(String)
    category = Column(String(30), default="general_chat")

    # Native pgvector 1536-dim Embedding Column for semantic search
    vector_embedding = Column(Vector(1536), nullable=True)
    memory_salience = Column(Float, default=1.0)  # Importance/relevance score
    
    # Structured metadata for memory organization
    # NOTE: attribute name cannot be `metadata` (reserved by SQLAlchemy Declarative API).
    metadata_json = Column("metadata", JSONB, default={})  # Tags, references, related IDs, etc.
    
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="memories")


class AthleteInsight(Base):
    __tablename__ = "athlete_insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    category = Column(String(50), nullable=False)
    insight_text = Column(String, nullable=False)
    confidence_score = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    
    # Structured insight metadata (JSONB)
    # NOTE: attribute name cannot be `metadata` (reserved by SQLAlchemy Declarative API).
    metadata_json = Column("metadata", JSONB, default={})  # Additional structured data (e.g., tags, related metrics)
    
    created_at = Column(DateTime, default=func.now())
    last_observed_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="insights")


class StravaToken(Base):
    __tablename__ = "strava_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    strava_athlete_id = Column(BigInteger, nullable=True, index=True)
    access_token = Column(String)
    refresh_token = Column(String)
    expires_at = Column(Integer)
    created_at = Column(DateTime, default=func.now())


class DailyReadiness(Base):
    __tablename__ = "daily_readiness"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    fatigue_score = Column(Float)
    recovery_score = Column(Float)
    injury_risk = Column(String)
    psychological_readiness = Column(Float, default=1.0)
    created_at = Column(DateTime, default=func.now())


class MedicalReport(Base):
    """Stores uploaded medical reports and extracted parameters"""
    __tablename__ = "medical_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    file_url = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=True)
    uploaded_at = Column(DateTime, default=func.now())
    extracted_data = Column(JSONB, default={})  # Extracted parameters from PDF
    vo2max = Column(Float, nullable=True)
    lactate_threshold = Column(Float, nullable=True)
    resting_hr = Column(Float, nullable=True)
    blood_pressure = Column(String(20), nullable=True)
    medications = Column(Text, nullable=True)
    limitations = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="medical_reports")


class PerformanceMetric(Base):
    """Daily/Weekly performance aggregates"""
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    metric_date = Column(DateTime, index=True)
    period_type = Column(String(20))  # 'daily', 'weekly', 'monthly'
    
    weekly_volume_km = Column(Float, default=0.0)
    weekly_tss = Column(Float, default=0.0)
    weekly_intensity_factor = Column(Float, default=0.0)
    avg_hr = Column(Float, nullable=True)
    avg_pace = Column(Float, nullable=True)
    
    form_score = Column(Float, nullable=True)  # -10 to +10
    fatigue_score = Column(Float, nullable=True)  # 0-100
    readiness_score = Column(Float, nullable=True)  # 0-100
    injury_risk_score = Column(Float, nullable=True)  # 0-100
    
    peak_power = Column(Integer, nullable=True)  # For cyclists
    total_workouts = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="performance_metrics")


class SubscriptionTier(Base):
    """Subscription plan tiers"""
    __tablename__ = "subscription_tiers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)  # 'Basic', 'Premium', 'Elite'
    price_usd = Column(Float)
    price_inr = Column(Float)
    features = Column(JSONB, default={})
    max_athletes = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())


class CoachingDecision(Base):
    """Track coaching recommendations and outcomes"""
    __tablename__ = "coaching_decisions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    decision_type = Column(String(50))  # 'plan_adjustment', 'rest_day', 'hard_effort', etc.
    recommendation = Column(String(500))
    user_followed = Column(Boolean, nullable=True)
    outcome = Column(String(200), nullable=True)
    effectiveness_score = Column(Float, nullable=True)  # 1-5
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)


class SafetyAlert(Base):
    __tablename__ = "safety_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    alert_type = Column(String(50), index=True)
    severity = Column(String(20), default="warning")
    message = Column(String(500))
    source_metric = Column(String(50), nullable=True)
    source_value = Column(Float, nullable=True)
    is_resolved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)
    resolved_at = Column(DateTime, nullable=True)


class AthleteLearning(Base):
    """Track learnings about athlete patterns"""
    __tablename__ = "athlete_learnings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    learning_key = Column(String(100))  # 'prefers_morning_runs', 'responds_to_volume', etc.
    learning_value = Column(JSONB)
    confidence_score = Column(Float, default=0.5)  # 0-1
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class InjuryIncident(Base):
    """Track injury history for prevention"""
    __tablename__ = "injury_incidents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    injury_type = Column(String(100))
    severity = Column(String(20))  # 'mild', 'moderate', 'severe'
    onset_date = Column(DateTime)
    recovery_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    related_activity_id = Column(Integer, ForeignKey("activities.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())


class PersonalRecord(Base):
    """Track athlete personal records"""
    __tablename__ = "personal_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    distance_km = Column(Float)
    pace_seconds_per_km = Column(Integer)
    time_seconds = Column(Integer)
    activity_id = Column(Integer, ForeignKey("activities.id"))
    race_date = Column(DateTime)
    created_at = Column(DateTime, default=func.now())


# Optimized Database Indices
Index("idx_activity_user_date", Activity.user_id, Activity.start_date_utc)
Index("idx_memory_user_category", CoachMemory.user_id, CoachMemory.category)
Index("idx_insights_user_category", AthleteInsight.user_id, AthleteInsight.category)
Index("idx_medical_report_user", MedicalReport.user_id)
Index("idx_performance_metric_user_date", PerformanceMetric.user_id, PerformanceMetric.metric_date)

# Additional indices for vector search and filtering
Index("idx_memory_user_salience", CoachMemory.user_id, CoachMemory.memory_salience)  # Vector search optimization
Index("idx_insight_active_category", AthleteInsight.user_id, AthleteInsight.is_active, AthleteInsight.category)
Index("idx_user_active_phase", User.is_active, User.training_phase)  # For athlete filtering
Index("idx_activity_type_user", Activity.user_id, Activity.type)  # For activity type filtering
Index("idx_coaching_decision_user_date", CoachingDecision.user_id, CoachingDecision.created_at)  # Recent decisions
Index("idx_athlete_learning_user_key", AthleteLearning.user_id, AthleteLearning.learning_key)  # Learning lookup
Index("idx_safety_alert_user_open", SafetyAlert.user_id, SafetyAlert.is_resolved)


class CoachingDecisionTrace(Base):
    """
    Immutable, explainable audit trail for a single coaching run.

    This is intentionally more detailed than `CoachingDecision` and is designed
    to support safety audits, explainability, and future replay tooling.
    """

    __tablename__ = "coaching_decision_traces"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)

    trigger_type = Column(String(30), nullable=True)  # 'webhook', 'scheduled', 'chat', etc.
    input_event_id = Column(String(200), nullable=True, index=True)

    # Deterministic inputs + outputs
    safety_context = Column(JSONB, default={})
    rules_fired = Column(JSONB, default=[])
    plan_before_safety = Column(JSONB, default={})
    plan_after_safety = Column(JSONB, default={})

    # LLM-related metadata (redactable)
    llm_prompt_summary = Column(JSONB, default={})
    llm_response_metadata = Column(JSONB, default={})

    correlation_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)

    user = relationship("User")


Index("idx_decision_trace_user_created", CoachingDecisionTrace.user_id, CoachingDecisionTrace.created_at)
Index("idx_decision_trace_user_event", CoachingDecisionTrace.user_id, CoachingDecisionTrace.input_event_id)


class ProcessedEvent(Base):
    """
    Idempotency ledger for event-driven processing.
    """

    __tablename__ = "processed_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(200), nullable=False, unique=True, index=True)
    source = Column(String(50), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)


class AICostEvent(Base):
    """
    Per-call cost and token usage events to support cost accounting and SaaS metering.
    """

    __tablename__ = "ai_cost_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    org_id = Column(String(50), nullable=True, index=True)
    feature = Column(String(50), nullable=True, index=True)  # 'chat', 'memory_compression', etc.
    provider = Column(String(30), nullable=True)
    model = Column(String(50), nullable=True, index=True)
    tokens_estimated = Column(Integer, nullable=True)
    cost_usd_estimated = Column(Float, nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=func.now(), index=True)


