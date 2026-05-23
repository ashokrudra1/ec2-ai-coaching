# backend/memory/memory_archiver.py
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from backend.models import CoachMemory, AthleteInsight
from backend.llm_fallback_service import llm_router

logger = logging.getLogger(__name__)

class MemoryArchivalEngine:
    @staticmethod
    def compress_old_memories(db: Session, user_id: int):
        """
        Compresses chat logs older than 14 days into a single consolidated episodic summary,
        then removes the old logs to keep the vector database small and fast.
        """
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        
        # Fetch old chat memories
        old_memories = (
            db.query(CoachMemory)
            .filter(
                CoachMemory.user_id == user_id,
                CoachMemory.created_at <= two_weeks_ago,
                CoachMemory.category == "general_chat"
            )
            .all()
        )
        
        if len(old_memories) < 15:
            return # Skip if there aren't enough logs to warrant compression

        # Concatenate chat logs for summarization
        memory_transcript = "\n".join([f"{m.role.upper()}: {m.content}" for m in old_memories])
        
        system_instruction = "You are an Elite Memory Compactor. Analyze the chat transcripts and extract critical athlete traits, injuries, goals, and coaching guidelines."
        prompt = f"Compact this transcript into exactly 3 bullet points:\n{memory_transcript}"
        
        try:
            # Generate the consolidated summary
            summary = llm_router.generate_completion(system_instruction, prompt, target_model="gpt-4o-mini")
            
            # Save the summarized insight
            consolidated_insight = AthleteInsight(
                user_id=user_id,
                category="archived_episodic_summary",
                insight_text=summary,
                confidence_score=0.95
            )
            db.add(consolidated_insight)
            
            # Delete the detailed raw logs
            for m in old_memories:
                db.delete(m)
                
            db.commit()
            logger.info(f"🧹 Compressed and archived {len(old_memories)} old memory logs for User {user_id}")
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to archive and compress memories: {str(e)}")
