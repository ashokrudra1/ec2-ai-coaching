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
            results = (
                db.query(CoachMemory)
                .filter(CoachMemory.user_id == user_id)
                .order_by(CoachMemory.vector_embedding.cosine_distance(query_vector))
                .limit(limit)
                .all()
            )

            if not results:
                return "No historical pattern memories saved yet."

            formatted_context = []
            for r in results:
                formatted_context.append(f"[{r.category.upper()} - {r.created_at.strftime('%Y-%m-%d')}]: {r.content}")

            return "\n".join(formatted_context)
        except Exception as e:
            logger.error(f"❌ Native vector retrieval crashed: {str(e)}")
            return "Historical patterns currently offline."
