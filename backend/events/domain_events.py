from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    event_id: str
    occurred_at: datetime
    user_id: Optional[int] = None
    payload: Dict[str, Any] = field(default_factory=dict)


def now_utc() -> datetime:
    # Keep simple; existing codebase uses naive UTC in places.
    return datetime.utcnow()


def workout_ingested(*, event_id: str, user_id: int, activity_id: int, payload: Dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type="WorkoutIngested",
        event_id=event_id,
        occurred_at=now_utc(),
        user_id=user_id,
        payload={"activity_id": activity_id, **(payload or {})},
    )


def athlete_state_updated(*, event_id: str, user_id: int, payload: Dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type="AthleteStateUpdated",
        event_id=event_id,
        occurred_at=now_utc(),
        user_id=user_id,
        payload=payload or {},
    )


def safety_alert_raised(*, event_id: str, user_id: int, payload: Dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type="SafetyAlertRaised",
        event_id=event_id,
        occurred_at=now_utc(),
        user_id=user_id,
        payload=payload or {},
    )


def plan_generated(*, event_id: str, user_id: int, payload: Dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type="PlanGenerated",
        event_id=event_id,
        occurred_at=now_utc(),
        user_id=user_id,
        payload=payload or {},
    )


def plan_overridden_for_risk(*, event_id: str, user_id: int, payload: Dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type="PlanOverriddenForRisk",
        event_id=event_id,
        occurred_at=now_utc(),
        user_id=user_id,
        payload=payload or {},
    )


def emergency_condition_detected(*, event_id: str, user_id: Optional[int], payload: Dict[str, Any]) -> DomainEvent:
    return DomainEvent(
        event_type="EmergencyConditionDetected",
        event_id=event_id,
        occurred_at=now_utc(),
        user_id=user_id,
        payload=payload or {},
    )

