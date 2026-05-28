from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.live_coaching.intervention_engine import LiveCoachingInterventionEngine, LiveSignal

router = APIRouter(prefix="/live-coaching", tags=["live-coaching"])


class LiveSignalPayload(BaseModel):
    avg_hr: float
    hr_threshold: float
    pace_sec_per_km: float
    target_pace_sec_per_km: float
    cardiac_drift: float
    heat_index_c: float = 20.0


@router.post("/interventions")
def evaluate_live_interventions(payload: LiveSignalPayload):
    signal = LiveSignal(**payload.model_dump())
    return {"interventions": LiveCoachingInterventionEngine.evaluate(signal)}
