# Autonomous Athlete OS Rollout Gates

## Phase Promotion Policy

Each phase must satisfy all gates before production promotion.

## Phase 1 Gate: Safety + Reliability

- Deterministic policy override tests pass.
- Idempotency duplicate replay tests pass.
- `/health` and `/health/metrics` return healthy payloads.
- `coach.safety.blocked`, `coach.plan.safety_override`, and `event_bus.publish.error` counters are observable.

## Phase 2 Gate: Scientific Correctness

- Adaptation forecast values are bounded to `[0, 1]`.
- Recovery and injury proxy calculations are deterministic and reproducible.
- Digital twin updates persist in PostgreSQL without nullable breakage.
- Race projection values are generated for activity ingest without runtime exceptions.

## Phase 3 Gate: Autonomous Behavior

- Proactive engagement task runs and emits deterministic messages.
- Real-time workout intervention hint triggers on high-risk telemetry.
- Council tone hint and safety arbitration appear in decision traces.

## Phase 4 Gate: SaaS Scale + Cost

- Org-level cost summary endpoint returns aggregated token/cost values.
- Celery queue routing includes proactive engagement workload.
- Cost events are persisted with estimated USD values when explicit cost is absent.

## Canary Rollout Strategy

1. Enable phase features for 5% of active tenants.
2. Observe 24 hours:
   - Error rate
   - Safety override rate
   - Message delivery success
   - Cost per athlete-day
3. Expand to 25%, 50%, then 100% with rollback at any sustained SLO breach.
