# backend/orchestration/coach_service.py
import logging
import json
import redis
from sqlalchemy.orm import Session
from backend.models import User
from backend.memory.semantic_memory import SemanticMemory
from backend.orchestration.decision_engine import DecisionEngine
from backend.sports_science.monitoring import AthleteMonitoringService
from backend.config.settings import settings
from backend.safety.policy_engine import SafetyContext, PolicyEngine
from backend.events.event_bus import event_bus
from backend.events import domain_events

# 🔐 SECURITY & COST GOVERNANCE IMPORTS
from backend.security.usage_governance import UsageGovernor
from backend.llm_fallback_service import llm_router
from backend.observability.metrics import measure_latency, record_counter

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(settings.REDIS_URL)

class CoachService:

    @staticmethod
    def generate(
        db: Session,
        user_id: int,
        user_input: str = None,
        activity_data=None,
        trigger_type: str = None,
        input_event_id: str = None,
        correlation_id: str = None,
    ) -> str:
        """
        Enterprise Orchestration Layer. Includes:
        - Multi-level Redis Caching
        - Cost-Governance Intelligent Model Routing
        - Semantic Vector Long-Term Memory
        - Pre-flight Token Quota verification & dynamic post-run tracking
        - Resilient Multi-Provider Fallback Routing (Outage Protection)
        """
        try:
            with measure_latency("coach.generate.latency_ms"):
                # ==========================================
                # 🎟️ 1. PRE-FLIGHT USAGE GOVERNANCE CHECK
                # ==========================================
                if UsageGovernor.is_quota_exceeded(db, user_id):
                    return "⚠️ You have reached your coaching limit for this month. Please upgrade your plan to unlock more runs."

                # ==========================================
                # ⚡ 2. CACHED ATHLETE SNAPSHOT ACCESS
                # ==========================================
                redis_key = f"cache:user_snapshot:{user_id}"
                cached_data = redis_client.get(redis_key)

                if cached_data:
                    snapshot = json.loads(cached_data)
                    logger.info("⚡ Snapshot cache HIT on Redis.")
                else:
                    user = db.query(User).filter_by(id=user_id).first()
                    if not user:
                        return "⚠️ Profile connection error."

                    # Database fallback & write back to cache
                    from backend.orchestration.athlete_state_builder import AthleteStateBuilder
                    snapshot = AthleteStateBuilder.build(db, user_id)
                    redis_client.setex(redis_key, 1800, json.dumps(snapshot))
                    logger.info("💾 Snapshot cache MISS. Re-built and written.")

            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return "⚠️ Profile connection error."
            AthleteMonitoringService.refresh_user_state(db, user)
            db.commit()
            snapshot.setdefault("fatigue_metrics", {})
            snapshot["fatigue_metrics"]["ctl"] = user.ctl
            snapshot["fatigue_metrics"]["atl"] = user.atl
            snapshot["fatigue_metrics"]["tsb"] = user.tsb

            # ==========================================
            # 🧠 3. LONG-TERM VECTOR MEMORY RETRIEVAL
            # ==========================================
            lookback_query = user_input or "latest training workload progression and recovery velocity"
            historical_context = SemanticMemory.retrieve_relevant_athlete_history(db, user_id, lookback_query, limit=3)

            # ==========================================
            # ⚖️ 4. DETerministic SAFETY EVALUATION
            # ==========================================
            predictive_risk = snapshot.get("predictive_risk", {}) or {}
            safety_ctx = SafetyContext(
                user_id=user.id,
                tsb=user.tsb or 0.0,
                ctl=user.ctl or 0.0,
                atl=user.atl or 0.0,
                injury_probability_14d=predictive_risk.get("injury_probability_14d", 0.0),
                burnout_probability_21d=predictive_risk.get("burnout_probability_21d", 0.0),
                recovery_score=snapshot.get("recovery_score", 100.0),
                has_high_risk_medical_flags=bool(user.medical_insights),
            )
            safety_decision = PolicyEngine.evaluate(safety_ctx)
            fatigue_guardrail_active = any(
                r.rule_id in {"fatigue_critical_tsb", "fatigue_caution_tsb"} for r in (safety_decision.rules_fired or [])
            )
            record_counter(
                "coach.safety.rules_fired.total",
                value=len(safety_decision.rules_fired or []),
                user_id=user_id,
            )

            # Preserve legacy fatigue guardrail alerts but have them go through PolicyEngine thresholds.
            if not safety_decision.allow_hard_training and (user.tsb or 0.0) < AthleteMonitoringService.TSB_CRITICAL:
                AthleteMonitoringService.ensure_fatigue_alert(db, user, user.tsb or 0.0)
                db.commit()

            # ==========================================
            # ⚖️ 5. DECISION ENGINE CO-ORDINATION
            # ==========================================
            council_diagnostics = DecisionEngine.generate_final_response(snapshot)
            arbitrated_plan = council_diagnostics["arbitrated_plan"]
            plan_before_safety = dict(arbitrated_plan)

            # Apply safety decision as a hard post-processor on the deterministic plan.
            if safety_decision.block_coaching:
                record_counter("coach.safety.blocked", user_id=user_id)
                return (
                    safety_decision.safety_message
                    or "Coaching is temporarily suspended due to safety rules. Please consult a medical professional."
                )

            # Respect max_intensity_zone by downgrading when necessary.
            plan_intensity = arbitrated_plan.get("final_intensity_zone", 1)
            if plan_intensity > safety_decision.max_intensity_zone:
                arbitrated_plan["final_intensity_zone"] = safety_decision.max_intensity_zone
                arbitrated_plan["is_overridden"] = True
                existing_reason = arbitrated_plan.get("override_reason") or ""
                safety_reason = safety_decision.safety_message or "Safety policy limited intensity today."
                arbitrated_plan["override_reason"] = f"{existing_reason} {safety_reason}".strip()
                record_counter("coach.plan.safety_override", user_id=user_id)

            # ==========================================
            # 🎭 6. PERSONA TONE MAPPING
            # ==========================================
            persona = user.coach_persona or "veda"
            tone_hint = None
            for objection in council_diagnostics.get("council", {}).get("objections", []):
                if objection.get("objection_id") == "tone_hint":
                    tone_hint = objection.get("metadata", {}).get("tone_style")
                    break
            if fatigue_guardrail_active:
                coaching_tone = "PERSONA: Injury-prevention endurance clinician. Calm, firm, safety-first, blocks intensity, explains recovery priority."
            elif tone_hint == "supportive":
                coaching_tone = "PERSONA: Supportive performance coach. Empathetic, clear, psychologically safe, with specific next steps."
            elif persona == "dev":
                coaching_tone = "PERSONA: Captain Dev. Military drill sergeant, blunt, demanding, strict compliance focus."
            elif persona == "priya":
                coaching_tone = "PERSONA: Coach Priya. Empathetic, supportive guide, warm, holistic wellness focus."
            else:
                coaching_tone = "PERSONA: Coach Veda. High-performance Olympic sports scientist, highly technical and analytical."

            # ==========================================
            # 🪙 6. MODEL ROUTING CONFIGURATION (COST CONTROL)
            # ==========================================
            target_model = "gpt-4o-mini"

            # Complex sports-science workouts, risk warnings, or overrides route to standard gpt-4o
            if (
                activity_data is not None or
                arbitrated_plan.get("is_overridden") is True or
                snapshot.get("predictive_risk", {}).get("injury_probability_14d", 0.0) > 0.60
            ):
                target_model = "gpt-4o"
                logger.info(f"🎯 Dynamic Routing: Elevated complexity detected. Model set to {target_model}")
            else:
                logger.info(f"🪙 Dynamic Routing: Standard communication. Model set to {target_model}")

            narrator_prompt = f"""
You are an elite endurance coach executing this profile:
{coaching_tone}

BIOMETRICS:
- CTL: {user.ctl} | ATL: {user.atl} | TSB: {user.tsb}
- Phase: {user.training_phase} (Week {user.macrocycle_week})
- Compliance Rate: {snapshot.get('behavioral', {}).get('compliance_rate', 'unknown')}
- Cardiac Decoupling: {snapshot.get('cardiovascular_trends', {}).get('latest_cardiac_decoupling', 0.0)}

SEMANTIC MEMORY:
{historical_context}

PREDICTIVE RISKS:
- Injury: {(snapshot.get('predictive_risk', {}).get('injury_probability_14d', 0.0) * 100)}%
- Burnout: {(snapshot.get('predictive_risk', {}).get('burnout_probability_21d', 0.0) * 100)}%

ARBITRATED PLAN:
- Workout: {arbitrated_plan['final_action']}
- Override: {arbitrated_plan['is_overridden']} (Reason: {arbitrated_plan['override_reason']})

RULES:
1. STRICT BREVITY: Output exactly 3 to 4 technical sentences (under 120 words).
2. NEVER print technical markers, JSON fields, scores, or AI rules. Speak directly to the athlete.
3. If override is active, do not prescribe intensity above Zone 1 and explicitly prioritize recovery.
"""

            # ==========================================
            # 📡 7. MULTI-PROVIDER FALLBACK COMPLETION
            # ==========================================
            system_instruction = "You are an elite sports coach speaking to your athlete."
            
            response = llm_router.generate_completion(
                system_instruction=system_instruction,
                prompt=narrator_prompt,
                target_model=target_model,
                temperature=0.3
            )
            record_counter("coach.llm.call.success", model=target_model, user_id=user_id)

            # ==========================================
            # 📈 8. TOKEN ACCOUNTING LOGGING
            # ==========================================
            # Approximately 1 token = 4 characters
            tokens_used = int((len(narrator_prompt) + len(response)) / 4)
            UsageGovernor.log_token_usage(db, user_id, tokens_used)
            try:
                UsageGovernor.log_cost_event(
                    db,
                    user_id=user_id,
                    org_id=user.org_id,
                    feature="chat",
                    provider="llm_router",
                    model=target_model,
                    tokens_estimated=tokens_used,
                    cost_usd_estimated=None,
                    correlation_id=correlation_id,
                )
            except Exception:
                pass

            # ==========================================
            # 🧾 9. COACHING DECISION TRACE (Explainability)
            # ==========================================
            try:
                from backend.models import CoachingDecisionTrace

                rules_fired = []
                for r in (safety_decision.rules_fired or []):
                    rules_fired.append(
                        {
                            "rule_id": r.rule_id,
                            "description": r.description,
                            "severity": r.severity,
                            "rationale": r.rationale,
                            "source_metrics": r.source_metrics,
                        }
                    )

                trace = CoachingDecisionTrace(
                    user_id=user_id,
                    trigger_type=trigger_type,
                    input_event_id=input_event_id,
                    correlation_id=correlation_id,
                    safety_context={
                        "user_id": safety_ctx.user_id,
                        "tsb": safety_ctx.tsb,
                        "ctl": safety_ctx.ctl,
                        "atl": safety_ctx.atl,
                        "acwr": safety_ctx.acwr,
                        "injury_probability_14d": safety_ctx.injury_probability_14d,
                        "burnout_probability_21d": safety_ctx.burnout_probability_21d,
                        "recovery_score": safety_ctx.recovery_score,
                        "has_high_risk_medical_flags": safety_ctx.has_high_risk_medical_flags,
                    },
                    rules_fired=rules_fired,
                    plan_before_safety=plan_before_safety,
                    plan_after_safety=arbitrated_plan,
                    llm_prompt_summary={
                        "persona": persona,
                        "target_model": target_model,
                        "rules_fired": [rf.get("rule_id") for rf in rules_fired],
                        "prompt_chars": len(narrator_prompt),
                        "historical_context_included": bool(historical_context),
                    },
                    llm_response_metadata={
                        "target_model": target_model,
                        "tokens_estimated": tokens_used,
                        "max_intensity_zone": safety_decision.max_intensity_zone,
                        "allow_hard_training": safety_decision.allow_hard_training,
                        "safety_message": safety_decision.safety_message,
                        "response_chars": len(response or ""),
                    },
                )
                db.add(trace)
                db.commit()
            except Exception:
                # Trace must never block athlete-facing coaching.
                logger.exception("Failed to write CoachingDecisionTrace")
                db.rollback()
                record_counter("coach.trace.write.error", user_id=user_id)

            try:
                event_bus.publish(
                    domain_events.plan_generated(
                        event_id=f"plan:{user_id}:{input_event_id or 'na'}:{correlation_id or 'na'}",
                        user_id=user_id,
                        payload={
                            "is_overridden": bool(arbitrated_plan.get("is_overridden")),
                            "final_intensity_zone": arbitrated_plan.get("final_intensity_zone"),
                            "target_model": target_model,
                            "tokens_estimated": tokens_used,
                        },
                    )
                )
                if arbitrated_plan.get("is_overridden"):
                    event_bus.publish(
                        domain_events.plan_overridden_for_risk(
                            event_id=f"override:{user_id}:{input_event_id or 'na'}:{correlation_id or 'na'}",
                            user_id=user_id,
                            payload={
                                "override_reason": arbitrated_plan.get("override_reason"),
                                "max_intensity_zone": safety_decision.max_intensity_zone,
                            },
                        )
                    )
            except Exception:
                # Event bus failures must not block coaching.
                record_counter("coach.event_bus.error", user_id=user_id)

            # ==========================================
            # 💾 10. SEMANTIC CHAT HISTORICAL COMMIT
            # ==========================================
            if user_input:
                SemanticMemory.write_semantic_memory(db, user_id, "user", user_input, "tactical")
                SemanticMemory.write_semantic_memory(db, user_id, "assistant", response, "tactical")

            return response

        except Exception as e:
            logger.error(f"❌ CoachService Execution failed: {str(e)}", exc_info=True)
            record_counter("coach.generate.error", user_id=user_id)
            return "⚠️ Core coaching systems currently recalibrating. Let's touch base in a moment."
