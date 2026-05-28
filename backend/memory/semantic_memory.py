# backend/memory/semantic_memory.py
import math
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import CoachMemory
from backend.llm_service import client
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class SemanticMemory:
    RECENCY_HALF_LIFE_DAYS = 14.0


    @staticmethod
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True
    )
    def get_embedding(text: str) -> list:
        try:
            response = client.embeddings.create(
                input=[text.replace("\n", " ")],
                model="text-embedding-3-small"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"⚠️ OpenAI Embedding failed: {str(e)}")
            raise e

    @staticmethod
    def write_semantic_memory(db: Session, user_id: int, role: str, content: str, category: str = "general_chat"):
        try:
            embedding = SemanticMemory.get_embedding(content)
            important_keywords = ["injury", "pain", "knee", "ache", "marathon", "goal", "doctor", "dislike", "rest"]
            salience = 0.5
            if any(kw in content.lower() for kw in important_keywords):
                salience = 0.95

            memory = CoachMemory(
                user_id=user_id,
                role=role,
                content=content,
                category=category,
                vector_embedding=embedding,
                memory_salience=salience
            )
            db.add(memory)
            db.commit()
            logger.info(f"🧠 Native pgvector memory saved for User {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to write vector memory: {str(e)}")

    @staticmethod
    def retrieve_relevant_athlete_history(db: Session, user_id: int, query_text: str, limit: int = 3) -> str:
        """
        Executes an extremely high-speed, native pgvector cosine distance query
        directly on PostgreSQL.
        """
        try:
            query_vector = SemanticMemory.get_embedding(query_text)
            
            # Using pgvector's native cosine distance operator '<=>' via SQLAlchemy
            raw_results = (
                db.query(CoachMemory)
                .filter(CoachMemory.user_id == user_id)
                .order_by(CoachMemory.vector_embedding.cosine_distance(query_vector))
                .limit(max(limit * 6, 12))
                .all()
            )

            if not raw_results:
                return "No historical pattern memories saved yet."

            now = datetime.utcnow()
            weighted = []
            for mem in raw_results:
                semantic_similarity = SemanticMemory._cosine_similarity(query_vector, mem.vector_embedding or [])
                age_days = max(0.0, (now - mem.created_at).total_seconds() / 86400.0) if mem.created_at else 30.0
                recency_decay = math.exp(-age_days / SemanticMemory.RECENCY_HALF_LIFE_DAYS)
                salience = float(mem.memory_salience or 0.5)
                injury_weight = 1.15 if any(k in (mem.content or "").lower() for k in ["injury", "pain", "ache", "strain"]) else 1.0
                behavior_weight = 1.1 if mem.category in {"tactical", "compliance", "injury"} else 1.0
                final_score = semantic_similarity * recency_decay * max(0.25, salience) * injury_weight * behavior_weight
                weighted.append((final_score, mem))

            weighted.sort(key=lambda x: x[0], reverse=True)
            results = [m for _, m in weighted[:limit]]

            formatted_context = []
            for r in results:
                formatted_context.append(f"[{r.category.upper()} - {r.created_at.strftime('%Y-%m-%d')}]: {r.content}")

            return "\n".join(formatted_context)
        except Exception as e:
            logger.error(f"❌ Native vector retrieval crashed: {str(e)}")
            return "Historical patterns currently offline."

    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
        norm_b = math.sqrt(sum(float(y) * float(y) for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))
