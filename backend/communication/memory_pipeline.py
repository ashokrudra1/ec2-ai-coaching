"""
Response-to-Memory Pipeline
Saves coaching exchanges to memory with semantic embeddings
Extracts athlete learnings from interactions
"""
import logging
import os
from typing import Dict, Optional, List, Tuple
from sqlalchemy.orm import Session
from openai import OpenAI
import re

from backend.models import CoachMemory, AthleteLearning
from backend.training_system.coach_memory_engine import CoachMemoryEngine
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


class MemoryPipeline:
    """
    Handles storing coaching exchanges and extracting athlete learnings
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize OpenAI client for embeddings"""
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = "text-embedding-3-small"

    def store_coaching_exchange(
        self, 
        db: Session, 
        user_id: int, 
        user_msg: str, 
        ai_response: str
    ) -> bool:
        """
        Store coaching exchange with embeddings for semantic search.
        
        Saves both user message and AI response to CoachMemory.
        Extracts embeddings for future semantic searches.
        """
        try:
            # Save user message
            user_memory_saved = CoachMemoryEngine.save_memory(
                db, user_id, "user", user_msg, category="coaching"
            )
            
            # Save AI response
            ai_memory_saved = CoachMemoryEngine.save_memory(
                db, user_id, "assistant", ai_response, category="coaching"
            )

            if not (user_memory_saved and ai_memory_saved):
                logger.warning(f"Memory save failed for user {user_id}")
                return False

            # Extract and store embeddings (graceful degradation if API fails)
            try:
                user_embedding = self._get_embedding(user_msg)
                ai_embedding = self._get_embedding(ai_response)

                # Update embeddings in database
                last_user_msg = db.query(CoachMemory).filter(
                    CoachMemory.user_id == user_id,
                    CoachMemory.role == "user",
                    CoachMemory.category == "coaching"
                ).order_by(CoachMemory.created_at.desc()).first()

                last_ai_msg = db.query(CoachMemory).filter(
                    CoachMemory.user_id == user_id,
                    CoachMemory.role == "assistant",
                    CoachMemory.category == "coaching"
                ).order_by(CoachMemory.created_at.desc()).first()

                if last_user_msg and user_embedding:
                    last_user_msg.vector_embedding = user_embedding
                
                if last_ai_msg and ai_embedding:
                    last_ai_msg.vector_embedding = ai_embedding

                db.commit()
                logger.info(f"✅ Embeddings stored for user {user_id}")

            except Exception as e:
                logger.warning(f"Embedding storage failed (non-critical): {e}")
                # Continue anyway - memory was saved

            return True

        except Exception as e:
            logger.error(f"❌ Memory storage error: {e}", exc_info=True)
            return False

    def extract_learnings(
        self, 
        user_msg: str, 
        ai_response: str
    ) -> Dict[str, Dict]:
        """
        Extract athlete learnings from coaching exchange.
        
        Examples:
        - "I prefer morning runs" → learning: prefers_morning_runs
        - "I feel better with low volume" → learning: responds_to_low_volume
        - "My knees hurt when I do speedwork" → learning: knees_vulnerable
        
        Returns dict of learning_key -> {value: ..., confidence: 0-1}
        """
        learnings = {}

        # Pattern 1: Time preferences
        if re.search(r"(prefer|usually|like).*(morning|afternoon|evening)", user_msg, re.I):
            match = re.search(r"(morning|afternoon|evening)", user_msg, re.I)
            if match:
                learnings["preferred_time_of_day"] = {
                    "value": match.group(1).lower(),
                    "confidence": 0.85
                }

        # Pattern 2: Pace/intensity preferences
        if re.search(r"(easier|more comfortable|better).*(slow|easy|zone 2)", user_msg, re.I):
            learnings["prefers_low_intensity"] = {
                "value": True,
                "confidence": 0.75
            }
        
        if re.search(r"(prefer|enjoy|good).*(fast|hard|interval|tempo)", user_msg, re.I):
            learnings["enjoys_high_intensity"] = {
                "value": True,
                "confidence": 0.75
            }

        # Pattern 3: Volume preferences
        if re.search(r"(too much|overwhelm|hard to keep up).*(running|training|distance)", user_msg, re.I):
            learnings["responds_to_low_volume"] = {
                "value": True,
                "confidence": 0.8
            }

        if re.search(r"(like|prefer|do well with).*(high volume|lots of|more)", user_msg, re.I):
            learnings["responds_to_high_volume"] = {
                "value": True,
                "confidence": 0.75
            }

        # Pattern 4: Injury vulnerabilities
        injury_keywords = {
            "knee": "knees_vulnerable",
            "ankle": "ankles_vulnerable",
            "shin": "shins_vulnerable",
            "hip": "hips_vulnerable",
            "hamstring": "hamstrings_vulnerable",
            "calf": "calves_vulnerable",
            "heel": "heels_vulnerable",
            "plantar fascia": "plantar_fasciitis_risk"
        }
        
        for keyword, learning_key in injury_keywords.items():
            if re.search(rf"({keyword}).*hurt|pain|issue|problem", user_msg, re.I):
                learnings[learning_key] = {
                    "value": True,
                    "confidence": 0.9
                }

        # Pattern 5: Training responses
        if re.search(r"(felt great|felt amazing|pr|personal record)", user_msg, re.I):
            # Extract what they did
            if re.search(r"(long run|easy run|tempo|interval|speedwork)", user_msg, re.I):
                workout_type = re.search(r"(long run|easy run|tempo|interval|speedwork)", user_msg, re.I).group(1)
                learnings[f"responds_well_to_{workout_type.replace(' ', '_')}"] = {
                    "value": True,
                    "confidence": 0.8
                }

        # Pattern 6: Psychological patterns
        if re.search(r"(frustrated|stressed|overwhelm|anxious|nervous)", user_msg, re.I):
            learnings["anxiety_prone"] = {
                "value": True,
                "confidence": 0.7
            }

        if re.search(r"(confident|excited|motivated|looking forward)", user_msg, re.I):
            learnings["high_motivation"] = {
                "value": True,
                "confidence": 0.7
            }

        # Pattern 7: Recovery preferences
        if re.search(r"(cross train|strength|yoga|mobility)", user_msg, re.I):
            learnings["uses_cross_training"] = {
                "value": True,
                "confidence": 0.75
            }

        # Pattern 8: Coach response effectiveness
        # If user is positive after coaching suggestion
        if re.search(r"(thanks|appreciate|helped|great advice|makes sense)", user_msg, re.I):
            learnings["responds_to_coaching"] = {
                "value": True,
                "confidence": 0.7
            }

        return learnings

    def update_athlete_model(
        self, 
        db: Session, 
        user_id: int, 
        learnings_dict: Dict[str, Dict]
    ) -> bool:
        """
        Update athlete learning model with discovered patterns.
        Only records high-confidence learnings (confidence > 0.7).
        """
        if not learnings_dict:
            return True

        try:
            recorded_count = 0

            for learning_key, learning_data in learnings_dict.items():
                confidence = learning_data.get("confidence", 0)
                
                # Only record high-confidence learnings
                if confidence < 0.7:
                    logger.debug(f"Skipping low-confidence learning: {learning_key} ({confidence})")
                    continue

                # Use CoachMemoryEngine to record learning
                success = CoachMemoryEngine.record_learning(
                    db, 
                    user_id,
                    learning_key,
                    learning_data.get("value"),
                    confidence
                )

                if success:
                    recorded_count += 1
                    logger.info(f"✅ Recorded learning: {learning_key} (conf: {confidence})")

            if recorded_count > 0:
                logger.info(f"Athlete model updated with {recorded_count} learnings")
            
            return True

        except Exception as e:
            logger.error(f"❌ Athlete model update error: {e}")
            return False

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding vector from OpenAI API.
        Returns None if API fails (graceful degradation).
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding

        except Exception as e:
            logger.warning(f"Embedding API error: {e}")
            return None

    def process_full_exchange(
        self, 
        db: Session, 
        user_id: int, 
        user_msg: str, 
        ai_response: str
    ) -> Dict:
        """
        Full pipeline: Store exchange + extract learnings + update model.
        
        Returns status dict with what was done.
        """
        try:
            result = {
                "success": True,
                "messages_stored": False,
                "learnings_extracted": 0,
                "learnings_recorded": 0
            }

            # Step 1: Store exchange
            if self.store_coaching_exchange(db, user_id, user_msg, ai_response):
                result["messages_stored"] = True

            # Step 2: Extract learnings
            learnings = self.extract_learnings(user_msg, ai_response)
            result["learnings_extracted"] = len(learnings)

            # Step 3: Update athlete model
            if learnings:
                if self.update_athlete_model(db, user_id, learnings):
                    result["learnings_recorded"] = len([l for l in learnings.values() if l.get("confidence", 0) > 0.7])

            logger.info(f"✅ Exchange processed for user {user_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Exchange processing error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
