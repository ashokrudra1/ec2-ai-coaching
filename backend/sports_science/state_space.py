import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Optional


@dataclass(frozen=True)
class TrainingStressEvent:
    event_date: datetime
    stress: float


@dataclass(frozen=True)
class TrainingLoadState:
    ctl: float
    atl: float
    tsb: float
    acwr: float
    fatigue_level: str
    injury_risk_score: float


class StateSpaceDecayModel:
    CTL_TAU_DAYS = 42.0
    ATL_TAU_DAYS = 7.0

    @staticmethod
    def decay_factor(days: float, tau_days: float) -> float:
        days = max(0.0, float(days or 0.0))
        tau_days = max(1.0, float(tau_days or 1.0))
        return math.exp(-days / tau_days)

    @classmethod
    def advance_state(
        cls,
        ctl: float,
        atl: float,
        stress: float,
        elapsed_days: float = 1.0,
        ctl_tau_days: float = CTL_TAU_DAYS,
        atl_tau_days: float = ATL_TAU_DAYS,
    ) -> TrainingLoadState:
        ctl_decay = cls.decay_factor(elapsed_days, ctl_tau_days)
        atl_decay = cls.decay_factor(elapsed_days, atl_tau_days)
        next_ctl = (ctl or 0.0) * ctl_decay + max(0.0, stress or 0.0) * (1.0 - ctl_decay)
        next_atl = (atl or 0.0) * atl_decay + max(0.0, stress or 0.0) * (1.0 - atl_decay)
        return cls.describe(next_ctl, next_atl)

    @classmethod
    def from_events(
        cls,
        events: Iterable[TrainingStressEvent],
        initial_ctl: float = 0.0,
        initial_atl: float = 0.0,
        start_date: Optional[datetime] = None,
        ctl_tau_days: float = CTL_TAU_DAYS,
        atl_tau_days: float = ATL_TAU_DAYS,
    ) -> TrainingLoadState:
        sorted_events = sorted(events, key=lambda item: item.event_date)
        ctl = initial_ctl or 0.0
        atl = initial_atl or 0.0
        previous_date = start_date

        for event in sorted_events:
            event_dt = cls._coerce_datetime(event.event_date)
            if previous_date is None:
                elapsed_days = 1.0
            else:
                elapsed_days = max(0.0, (event_dt - previous_date).total_seconds() / 86400.0)
            state = cls.advance_state(ctl, atl, event.stress, elapsed_days, ctl_tau_days, atl_tau_days)
            ctl, atl = state.ctl, state.atl
            previous_date = event_dt

        return cls.describe(ctl, atl)

    @classmethod
    def decay_to_date(
        cls,
        ctl: float,
        atl: float,
        last_updated_at: Optional[datetime],
        target_date: Optional[datetime] = None,
        ctl_tau_days: float = CTL_TAU_DAYS,
        atl_tau_days: float = ATL_TAU_DAYS,
    ) -> TrainingLoadState:
        if not last_updated_at:
            return cls.describe(ctl or 0.0, atl or 0.0)
        target = cls._coerce_datetime(target_date or datetime.now(timezone.utc))
        last = cls._coerce_datetime(last_updated_at)
        elapsed_days = max(0.0, (target - last).total_seconds() / 86400.0)
        return cls.advance_state(ctl or 0.0, atl or 0.0, 0.0, elapsed_days, ctl_tau_days, atl_tau_days)

    @staticmethod
    def describe(ctl: float, atl: float) -> TrainingLoadState:
        ctl = round(max(0.0, ctl or 0.0), 2)
        atl = round(max(0.0, atl or 0.0), 2)
        tsb = round(ctl - atl, 2)
        acwr = round(atl / ctl, 2) if ctl > 0 else 0.0
        if tsb < -20.0:
            fatigue_level = "critical"
        elif tsb < -10.0:
            fatigue_level = "high"
        elif tsb < -5.0:
            fatigue_level = "elevated"
        elif tsb <= 10.0:
            fatigue_level = "balanced"
        else:
            fatigue_level = "fresh"

        injury_risk_score = 0.10
        if tsb < -20.0 or acwr > 1.5:
            injury_risk_score = 0.72
        elif tsb < -10.0 or acwr >= 1.2:
            injury_risk_score = 0.45
        elif acwr < 0.8 and ctl > 0:
            injury_risk_score = 0.18

        return TrainingLoadState(
            ctl=ctl,
            atl=atl,
            tsb=tsb,
            acwr=acwr,
            fatigue_level=fatigue_level,
            injury_risk_score=round(injury_risk_score, 2),
        )

    @staticmethod
    def _coerce_datetime(value: datetime | date) -> datetime:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
