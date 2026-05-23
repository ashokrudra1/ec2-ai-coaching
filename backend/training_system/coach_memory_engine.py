"""
Coach Memory System
Retrieves athlete context before generating responses
Uses pgVector for semantic search of relevant memories
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.models import User, CoachMemory, AthleteLearning, InjuryIncident
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


class CoachMemoryEngine:
    """
    Manages athlete context, memories, and coaching history
    """

    @staticmethod
    def save_memory(
        db: Session,
        user_id: int,
        role: str,
        content: str,
        category: str = "general_chat",
        embedding: Optional[List[float]] = None,
    ) -> bool:
        """
        Save conversation message to memory
        """
        try:
            memory = CoachMemory(
                user_id=user_id,
                role=role,
                content=content,
                category=category,
            )

            # Store embedding if provided (for semantic search)
            if embedding:
                from pgvector.sqlalchemy import Vector

                memory.vector_embedding = embedding

            db.add(memory)
            db.commit()

            logger.info(f"✅ Memory saved for user {user_id}: {category}")
            return True

        except Exception as e:
            logger.error(f"❌ Memory save error: {e}")
            db.rollback()
            return False

    @staticmethod
    def retrieve_recent_context(
        db: Session, user_id: int, context_type: str = "all", limit: int = 10
    ) -> List[Dict]:
        """
        Retrieve recent conversation history for user
        """
        try:
            query = db.query(CoachMemory).filter_by(user_id=user_id)

            if context_type != "all":
                query = query.filter_by(category=context_type)

            memories = query.order_by(CoachMemory.created_at.desc()).limit(limit).all()

            context = []
            for memory in reversed(memories):  # Reverse to chronological order
                context.append(
                    {
                        "role": memory.role,
                        "content": memory.content,
                        "timestamp": memory.created_at.isoformat(),
                        "category": memory.category,
                    }
                )

            return context

        except Exception as e:
            logger.error(f"❌ Context retrieval error: {e}")
            return []

    @staticmethod
    def search_semantic_memories(
        db: Session, user_id: int, query_embedding: List[float], top_k: int = 5
    ) -> List[Dict]:
        """
        Semantic search for relevant memories using pgVector
        Uses cosine similarity
        """
        try:
            from sqlalchemy import text

            # Raw SQL query for pgVector similarity search
            query_sql = f"""
            SELECT id, content, role, category, created_at,
                   1 - (vector_embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM coach_memory
            WHERE user_id = :user_id
              AND vector_embedding IS NOT NULL
            ORDER BY vector_embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """

            results = db.execute(
                text(query_sql),
                {
                    "embedding": f"[{','.join(map(str, query_embedding))}]",
                    "user_id": user_id,
                    "top_k": top_k,
                },
            )

            memories = []
            for row in results:
                memories.append(
                    {
                        "id": row[0],
                        "content": row[1],
                        "role": row[2],
                        "category": row[3],
                        "timestamp": row[4].isoformat() if row[4] else None,
                        "similarity": float(row[5]),
                    }
                )

            logger.info(f"✅ Found {len(memories)} semantic matches for user {user_id}")
            return memories

        except Exception as e:
            logger.error(f"❌ Semantic search error: {e}")
            return []

    @staticmethod
    def get_athlete_learnings(db: Session, user_id: int) -> Dict:
        """
        Retrieve accumulated learnings about athlete patterns
        """
        try:
            learnings = db.query(AthleteLearning).filter_by(user_id=user_id).all()

            athlete_model = {}
            for learning in learnings:
                athlete_model[learning.learning_key] = {
                    "value": learning.learning_value,
                    "confidence": learning.confidence_score,
                    "updated": learning.updated_at.isoformat(),
                }

            return athlete_model

        except Exception as e:
            logger.error(f"❌ Athlete learning retrieval error: {e}")
            return {}

    @staticmethod
    def record_learning(
        db: Session, user_id: int, learning_key: str, learning_value: Dict, confidence: float = 0.5
    ) -> bool:
        """
        Record a new learning about athlete patterns
        Examples:
        - prefers_morning_runs: {bool: true}
        - responds_to_volume: {bool: true}
        - burnout_tendency: {threshold_weeks: 12}
        """
        try:
            existing = db.query(AthleteLearning).filter_by(user_id=user_id, learning_key=learning_key).first()

            if existing:
                existing.learning_value = learning_value
                existing.confidence_score = confidence
                existing.updated_at = datetime.now(timezone.utc)
            else:
                learning = AthleteLearning(
                    user_id=user_id,
                    learning_key=learning_key,
                    learning_value=learning_value,
                    confidence_score=confidence,
                )
                db.add(learning)

            db.commit()
            logger.info(f"✅ Learning recorded: {learning_key} (confidence: {confidence})")
            return True

        except Exception as e:
            logger.error(f"❌ Learning record error: {e}")
            db.rollback()
            return False

    @staticmethod
    def get_injury_history(db: Session, user_id: int) -> List[Dict]:
        """
        Retrieve athlete's injury history for context
        """
        try:
            injuries = db.query(InjuryIncident).filter_by(user_id=user_id).order_by(InjuryIncident.onset_date.desc()).all()

            history = []
            for injury in injuries:
                history.append(
                    {
                        "injury_type": injury.injury_type,
                        "severity": injury.severity,
                        "onset_date": injury.onset_date.isoformat(),
                        "recovery_date": injury.recovery_date.isoformat() if injury.recovery_date else None,
                        "days_to_recovery": (injury.recovery_date - injury.onset_date).days
                        if injury.recovery_date
                        else None,
                        "notes": injury.notes,
                    }
                )

            return history

        except Exception as e:
            logger.error(f"❌ Injury history retrieval error: {e}")
            return []

    @staticmethod
    def detect_burnout_risk(db: Session, user_id: int) -> Tuple[bool, float, str]:
        """
        Detect burnout risk based on athlete learnings and recent activity
        Returns: (is_at_risk, risk_score, reason)
        """
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return False, 0.0, "User not found"

            # Check psychological state
            psychological = user.psychological_twin or {}
            burnout_risk_internal = psychological.get("burnout_risk", 0.05)

            if burnout_risk_internal > 0.5:
                return True, burnout_risk_internal, "High internal burnout indicators"

            # Check compliance trends
            recent_memories = CoachMemoryEngine.retrieve_recent_context(db, user_id, limit=30)
            declined_attempts = sum(
                1 for m in recent_memories if "too tired" in m.get("content", "").lower() or "skip" in m.get("content", "").lower()
            )

            if declined_attempts > 5:
                risk_score = min(1.0, 0.2 + (declined_attempts * 0.1))
                return True, risk_score, f"Multiple workout declines ({declined_attempts} in recent messages)"

            # Check for rapid volume increases without recovery
            learnings = CoachMemoryEngine.get_athlete_learnings(db, user_id)

            # Check if athlete has burnout tendency from past
            if learnings.get("burnout_tendency"):
                threshold = learnings["burnout_tendency"].get("threshold_weeks", 12)
                risk_score = min(1.0, 0.3 + (1 / threshold) * 0.5)
                return True, risk_score, "Known burnout tendency detected"

            return False, 0.0, "No burnout risk detected"

        except Exception as e:
            logger.error(f"❌ Burnout detection error: {e}")
            return False, 0.5, str(e)


class ContextAssembler:
    """
    Assembles full athlete context for LLM coaching response
    """

    @staticmethod
    def assemble_coaching_context(db: Session, user_id: int) -> Dict:
        """
        Gather all relevant athlete context for coaching response
        """
        try:
            user = db.query(User).filter_by(id=user_id).first()
            if not user:
                return {"error": "User not found"}

            # Get current athlete state
            snapshot = user.precomputed_snapshot or {}

            # Get recent chat history
            recent_chat = CoachMemoryEngine.retrieve_recent_context(db, user_id, limit=5)

            # Get athlete learnings
            learnings = CoachMemoryEngine.get_athlete_learnings(db, user_id)

            # Get injury history
            injuries = CoachMemoryEngine.get_injury_history(db, user_id)

            # Check burnout risk
            burnout_at_risk, burnout_score, burnout_reason = CoachMemoryEngine.detect_burnout_risk(db, user_id)

            context = {
                "athlete": {
                    "name": user.name,
                    "age": user.age,
                    "experience": user.experience_level,
                    "goal": user.target_goal,
                    "subscription_plan": user.subscription_plan,
                },
                "current_state": {
                    "ctl": snapshot.get("ctl", 0),
                    "atl": snapshot.get("atl", 0),
                    "tsb": snapshot.get("tsb", 0),
                    "readiness": snapshot.get("readiness", 0),
                    "injury_risk": snapshot.get("injury_risk", 0),
                    "training_phase": user.training_phase,
                },
                "metrics": {
                    "vo2max": snapshot.get("vo2max"),
                    "hr_zones": snapshot.get("hr_zones"),
                    "weekly": snapshot.get("weekly", {}),
                    "personal_records": snapshot.get("personal_records", {}),
                    "training_age_years": snapshot.get("training_age", 0),
                },
                "recent_chat": recent_chat,
                "athlete_model": learnings,
                "injury_history": injuries,
                "burnout_risk": {
                    "at_risk": burnout_at_risk,
                    "score": burnout_score,
                    "reason": burnout_reason,
                },
                "psychological_state": user.psychological_twin,
                "behavioral_patterns": user.behavioral_twin,
                "medical_insights": user.medical_insights,
            }

            logger.info(f"✅ Coaching context assembled for user {user_id}")
            return context

        except Exception as e:
            logger.error(f"❌ Context assembly error: {e}")
            return {"error": str(e)}

    @staticmethod
    def format_context_for_llm(context: Dict) -> str:
        """
        Format assembled context into readable text for LLM system prompt
        """
        try:
            if "error" in context:
                return f"Error: {context['error']}"

            athlete = context.get("athlete", {})
            state = context.get("current_state", {})
            metrics = context.get("metrics", {})
            learnings = context.get("athlete_model", {})

            formatted = f"""
ATHLETE PROFILE:
- Name: {athlete.get('name', 'Unknown')}
- Age: {athlete.get('age', '?')} years
- Experience: {athlete.get('experience', 'Unknown')}
- Primary Goal: {athlete.get('goal', 'General fitness')}
- Current Phase: {state.get('training_phase', 'Base')}

CURRENT ATHLETIC STATE:
- Chronic Training Load (CTL): {state.get('ctl', 0):.1f}
- Acute Training Load (ATL): {state.get('atl', 0):.1f}
- Training Stress Balance (TSB): {state.get('tsb', 0):.1f}
- Readiness Score: {state.get('readiness', 0):.0f}/100
- Injury Risk: {state.get('injury_risk', 0):.0f}/100

PERFORMANCE METRICS:
- VO2Max (estimated): {metrics.get('vo2max', '?')} ml/kg/min
- Weekly Volume: {metrics.get('weekly', {}).get('volume_km', 0):.1f} km
- Weekly TSS: {metrics.get('weekly', {}).get('tss', 0):.1f}
- Workouts This Week: {metrics.get('weekly', {}).get('workout_count', 0)}

KEY ATHLETE PATTERNS:
{chr(10).join([f"- {k}: {v.get('value')} (confidence: {v.get('confidence')*100:.0f}%)" for k, v in learnings.items()[:5]])}

RECENT COMMUNICATION:
{chr(10).join([f"- [{m.get('role', 'user')}]: {m.get('content', '')[:100]}..." for m in context.get('recent_chat', [])[:3]])}
"""

            return formatted

        except Exception as e:
            logger.error(f"❌ Context formatting error: {e}")
            return "Error formatting context"
