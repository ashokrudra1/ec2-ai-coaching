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

    # Training Stress Metrics (CTL/ATL/TSB)
    atl = Column(Float, default=0.0)   # Acute Training Load (7-day decay)
    ctl = Column(Float, default=0.0)   # Chronic Training Load (42-day decay)
    tsb = Column(Float, default=0.0)   # Training Stress Balance

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
    max_hr = Column(Float, default=190.0)
    rest_hr = Column(Float, default=60.0)
    medical_insights = Column(Text, nullable=True)

    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    activities = relationship("Activity", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("CoachMemory", back_populates="user", cascade="all, delete-orphan")
    insights = relationship("AthleteInsight", back_populates="user", cascade="all, delete-orphan")


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

    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="activities")


class CoachMemory(Base):
    __tablename__ = "coach_memory"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    role = Column(String(20)) # 'user', 'assistant', 'system'
    content = Column(String)
    category = Column(String(30), default="general_chat")

    # Native pgvector 1536-dim Embedding Column
    vector_embedding = Column(Vector(1536), nullable=True)
    memory_salience = Column(Float, default=1.0)

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
    created_at = Column(DateTime, default=func.now())
    last_observed_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="insights")


class StravaToken(Base):
    __tablename__ = "strava_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    athlete_id = Column(BigInteger, nullable=True, index=True)
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


# Optimized Database Indices
Index("idx_activity_user_date", Activity.user_id, Activity.start_date_utc)
Index("idx_memory_user_category", CoachMemory.user_id, CoachMemory.category)
Index("idx_insights_user_category", AthleteInsight.user_id, AthleteInsight.category)
