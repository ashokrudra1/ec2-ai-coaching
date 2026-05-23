# backend/orchestration/coach_service.py
import logging
import json
import redis
from sqlalchemy.orm import Session
from backend.models import User
from backend.memory.semantic_memory import SemanticMemory
from backend.orchestration.decision_engine import DecisionEngine
from backend.config.settings import settings

# 🔐 SECURITY & COST GOVERNANCE IMPORTS
from backend.security.usage_governance import UsageGovernor
from backend.llm_fallback_service import llm_router

logger = logging.getLogger(__name__)
redis_client = redis.Redis.from_url(settings.REDIS_URL)

class CoachService:

    @staticmethod
    def generate(db: Session, user_id: int, user_input: str = None, activity_data = None) -> str:
        """
        Enterprise Orchestration Layer. Includes:
        - Multi-level Redis Caching
        - Cost-Governance Intelligent Model Routing
        - Semantic Vector Long-Term Memory
        - Pre-flight Token Quota verification & dynamic post-run tracking
        - Resilient Multi-Provider Fallback Routing (Outage Protection)
        """
        try:
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

            # ==========================================
            # 🧠 3. LONG-TERM VECTOR MEMORY RETRIEVAL
            # ==========================================
            lookback_query = user_input or "latest training workload progression and recovery velocity"
            historical_context = SemanticMemory.retrieve_relevant_athlete_history(db, user_id, lookback_query, limit=3)

            # ==========================================
            # ⚖️ 4. DECISION ENGINE CO-ORDINATION
            # ==========================================
            council_diagnostics = DecisionEngine.generate_final_response(snapshot)
            arbitrated_plan = council_diagnostics["arbitrated_plan"]

            # ==========================================
            # 🎭 5. PERSONA TONE MAPPING
            # ==========================================
            persona = user.coach_persona or "veda"
            if persona == "dev":
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

SEMANTIC MEMORY:
{historical_context}

PREDICTIVE RISKS:
- Injury: {snapshot['predictive_risk']['injury_probability_14d'] * 100}%
- Burnout: {snapshot['predictive_risk']['burnout_probability_21d'] * 100}%

ARBITRATED PLAN:
- Workout: {arbitrated_plan['final_action']}
- Override: {arbitrated_plan['is_overridden']} (Reason: {arbitrated_plan['override_reason']})

RULES:
1. STRICT BREVITY: Output exactly 3 to 4 technical sentences (under 120 words).
2. NEVER print technical markers, JSON fields, scores, or AI rules. Speak directly to the athlete.
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

            # ==========================================
            # 📈 8. TOKEN ACCOUNTING LOGGING
            # ==========================================
            # Approximately 1 token = 4 characters
            tokens_used = int((len(narrator_prompt) + len(response)) / 4)
            UsageGovernor.log_token_usage(db, user_id, tokens_used)

            # ==========================================
            # 💾 9. SEMANTIC CHAT HISTORICAL COMMIT
            # ==========================================
            if user_input:
                SemanticMemory.write_semantic_memory(db, user_id, "user", user_input, "tactical")
                SemanticMemory.write_semantic_memory(db, user_id, "assistant", response, "tactical")

            return response

        except Exception as e:
            logger.error(f"❌ CoachService Execution failed: {str(e)}", exc_info=True)
            return "⚠️ Core coaching systems currently recalibrating. Let's touch base in a moment."
