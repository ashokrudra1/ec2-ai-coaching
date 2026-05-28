import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import CoachingDecisionTrace

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coach/decision-trace", tags=["decision-trace"])


def _redact_for_athlete(trace: CoachingDecisionTrace) -> dict:
    return {
        "id": trace.id,
        "user_id": trace.user_id,
        "trigger_type": trace.trigger_type,
        "input_event_id": trace.input_event_id,
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
        "safety": {
            "safety_message": (trace.llm_response_metadata or {}).get("safety_message"),
            "max_intensity_zone": (trace.llm_response_metadata or {}).get("max_intensity_zone"),
            "rules_fired": [
                {
                    "rule_id": r.get("rule_id"),
                    "severity": r.get("severity"),
                    "description": r.get("description"),
                    "rationale": r.get("rationale"),
                }
                for r in (trace.rules_fired or [])
            ],
        },
        "plan": trace.plan_after_safety or {},
    }


@router.get("/{trace_id}")
def get_decision_trace(
    trace_id: int,
    audience: str = Query(default="athlete", pattern="^(athlete|internal)$"),
    db: Session = Depends(get_db),
):
    trace = db.query(CoachingDecisionTrace).filter(CoachingDecisionTrace.id == trace_id).first()
    if not trace:
        return {"error": "not_found"}

    if audience == "internal":
        return {
            "id": trace.id,
            "user_id": trace.user_id,
            "trigger_type": trace.trigger_type,
            "input_event_id": trace.input_event_id,
            "correlation_id": trace.correlation_id,
            "created_at": trace.created_at.isoformat() if trace.created_at else None,
            "safety_context": trace.safety_context or {},
            "rules_fired": trace.rules_fired or [],
            "plan_before_safety": trace.plan_before_safety or {},
            "plan_after_safety": trace.plan_after_safety or {},
            "llm_prompt_summary": trace.llm_prompt_summary or {},
            "llm_response_metadata": trace.llm_response_metadata or {},
        }

    return _redact_for_athlete(trace)


@router.get("/latest")
def get_latest_decision_trace(
    user_id: Optional[int] = Query(default=None),
    audience: str = Query(default="athlete", pattern="^(athlete|internal)$"),
    db: Session = Depends(get_db),
):
    q = db.query(CoachingDecisionTrace)
    if user_id is not None:
        q = q.filter(CoachingDecisionTrace.user_id == user_id)

    trace = q.order_by(CoachingDecisionTrace.created_at.desc(), CoachingDecisionTrace.id.desc()).first()
    if not trace:
        return {"error": "not_found"}

    if audience == "internal":
        return {
            "id": trace.id,
            "user_id": trace.user_id,
            "trigger_type": trace.trigger_type,
            "input_event_id": trace.input_event_id,
            "correlation_id": trace.correlation_id,
            "created_at": trace.created_at.isoformat() if trace.created_at else None,
            "safety_context": trace.safety_context or {},
            "rules_fired": trace.rules_fired or [],
            "plan_before_safety": trace.plan_before_safety or {},
            "plan_after_safety": trace.plan_after_safety or {},
            "llm_prompt_summary": trace.llm_prompt_summary or {},
            "llm_response_metadata": trace.llm_response_metadata or {},
        }

    return _redact_for_athlete(trace)


@router.get("/stats/summary")
def get_decision_trace_summary(
    user_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(CoachingDecisionTrace)
    if user_id is not None:
        q = q.filter(CoachingDecisionTrace.user_id == user_id)

    rows = q.order_by(CoachingDecisionTrace.created_at.desc()).limit(1000).all()
    total = len(rows)
    overridden = sum(1 for row in rows if bool((row.plan_after_safety or {}).get("is_overridden")))
    return {
        "total_traces": total,
        "overridden_traces": overridden,
        "override_rate": round((overridden / total), 4) if total else 0.0,
    }

