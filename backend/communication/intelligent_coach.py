"""
Intelligent Coach Response System
Bridges coach memory context to LLM-generated coaching responses
Provides personalized, context-aware coaching via OpenAI API
"""
import logging
import os
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from openai import OpenAI

from backend.models import User, CoachMemory, Activity, PerformanceMetric
from backend.training_system.coach_memory_engine import ContextAssembler, CoachMemoryEngine
from backend.database import SessionLocal

logger = logging.getLogger(__name__)


class IntelligentCoach:
    """
    Generates personalized coaching responses using LLM + athlete context
    """

    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize OpenAI client"""
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4"
        self.max_tokens = 300

    def generate_response(self, db: Session, user_id: int, user_message: str) -> Dict:
        """
        Generate intelligent coaching response

        Flow:
        1. Assemble full athlete context
        2. Build system prompt with context
        3. Call LLM with conversation
        4. Save response to memory
        5. Return to user
        """
        try:
            # Step 1: Assemble athlete context
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            
            if "error" in context:
                logger.error(f"Context assembly failed: {context['error']}")
                return {"success": False, "error": context["error"]}

            # Step 2: Build system prompt
            system_prompt = self._build_system_prompt(context)

            # Step 3: Get recent conversation history
            recent_chat = CoachMemoryEngine.retrieve_recent_context(db, user_id, limit=6)
            
            # Build messages for OpenAI
            messages = []
            
            # Add context alerts if needed
            if context.get("burnout_risk", {}).get("at_risk"):
                messages.append({
                    "role": "system",
                    "content": f"⚠️ ALERT: {context['burnout_risk'].get('reason', 'fatigue')} (Risk: {context['burnout_risk'].get('score', 0)*100:.0f}%)"
                })
            
            if context.get("current_state", {}).get("injury_risk", 0) > 60:
                messages.append({
                    "role": "system",
                    "content": f"⚠️ Injury Risk High ({context['current_state']['injury_risk']:.0f}/100) - Consider recovery"
                })

            # Add recent conversation
            for msg in recent_chat:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

            # Add current user message
            messages.append({
                "role": "user",
                "content": user_message
            })

            # Step 4: Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=0.7,
                top_p=0.9
            )

            coach_response = response.choices[0].message.content

            # Step 5: Save to memory
            CoachMemoryEngine.save_memory(
                db, user_id, "user", user_message, category="coaching"
            )
            CoachMemoryEngine.save_memory(
                db, user_id, "assistant", coach_response, category="coaching"
            )

            logger.info(f"✅ Coaching response generated for user {user_id}")

            return {
                "success": True,
                "response": coach_response,
                "context_summary": {
                    "readiness": context.get("current_state", {}).get("readiness"),
                    "injury_risk": context.get("current_state", {}).get("injury_risk"),
                    "burnout_at_risk": context.get("burnout_risk", {}).get("at_risk"),
                    "tsb": context.get("current_state", {}).get("tsb"),
                }
            }

        except Exception as e:
            logger.error(f"❌ Response generation error: {e}", exc_info=True)
            return {
                "success": False, 
                "error": str(e),
                "fallback_message": "I'm analyzing your data. Let me get back to you shortly!"
            }

    @staticmethod
    def _build_system_prompt(context: Dict) -> str:
        """
        Build comprehensive system prompt with athlete context
        """
        athlete = context.get("athlete", {})
        state = context.get("current_state", {})
        metrics = context.get("metrics", {})
        learnings = context.get("athlete_model", {})
        injuries = context.get("injury_history", [])
        psychological = context.get("psychological_state", {})

        experience = athlete.get("experience", "Intermediate")
        goal = athlete.get("goal", "General fitness")

        # Format learnings
        learning_text = ""
        if learnings:
            learning_lines = [
                f"- {k}: {v.get('value')} (Confidence: {v.get('confidence', 0)*100:.0f}%)" 
                for k, v in list(learnings.items())[:5]
            ]
            learning_text = "\n".join(learning_lines)
        else:
            learning_text = "- No patterns recorded yet"

        # Format injuries
        injury_text = ""
        if injuries:
            injury_lines = [
                f"- {inj.get('injury_type', 'Unknown')} ({inj.get('severity', 'Unknown')}): "
                f"{inj.get('onset_date', '?')} - {inj.get('recovery_date', 'ONGOING')}"
                for inj in injuries[-3:]
            ]
            injury_text = "\n".join(injury_lines)
        else:
            injury_text = "- No previous injuries recorded"

        prompt = f"""
You are an elite, experienced running coach with 20+ years of coaching professional and amateur endurance athletes.
Your name is AI Coach. You have deep expertise in periodization, physiological adaptations, injury prevention, and athlete psychology.

CURRENT ATHLETE PROFILE:
- Name: {athlete.get('name', 'Athlete')}
- Age: {athlete.get('age', '?')} years
- Experience Level: {experience}
- Primary Goal: {goal}
- Current Training Phase: {state.get('training_phase', 'Base')}
- Subscription: {athlete.get('subscription_plan', 'Free')} plan

ATHLETE'S CURRENT ATHLETIC STATE:
- Chronic Training Load (CTL): {state.get('ctl', 0):.1f} (baseline fitness)
- Acute Training Load (ATL): {state.get('atl', 0):.1f} (recent stress)
- Training Stress Balance (TSB): {state.get('tsb', 0):.1f} (fatigue indicator: +ve=fresh, -ve=fatigued)
- Readiness Score: {state.get('readiness', 0):.0f}/100 (training readiness)
- Injury Risk Score: {state.get('injury_risk', 0):.0f}/100 (injury susceptibility)
- Form Score: {state.get('form_score', 0):.1f}

PERFORMANCE METRICS:
- Estimated VO2Max: {metrics.get('vo2max', '?')} ml/kg/min
- Weekly Volume: {metrics.get('weekly', {}).get('volume_km', 0):.1f} km
- Weekly TSS: {metrics.get('weekly', {}).get('tss', 0):.0f}
- Workouts This Week: {metrics.get('weekly', {}).get('workout_count', 0)}
- Training Age: {metrics.get('training_age_years', 0)} years

ATHLETE'S DISCOVERED PATTERNS:
{learning_text}

INJURY HISTORY:
{injury_text}

PSYCHOLOGICAL STATE:
- Confidence: {psychological.get('confidence', 0.5)*100:.0f}%
- Anxiety: {psychological.get('anxiety', 0.3)*100:.0f}%
- Motivation: {psychological.get('motivation', 0.7)*100:.0f}%
- Burnout Risk: {psychological.get('burnout_risk', 0.05)*100:.0f}%
- Adherence: {psychological.get('adherence_velocity', 1.0):.2f}x

COACHING DIRECTIVES:
1. **Personalization**: Reference their goals, patterns, and history
2. **Science-Based**: Use CTL/ATL/TSB and readiness for recommendations
3. **Brief**: Keep under 150 words, actionable advice only
4. **Safety**: TSB < -30 or injury risk > 70 = recommend recovery/rest
5. **Progression**: TSB > 5 and readiness > 70 = ready for hard efforts
6. **Psychology**: Adapt tone to their motivation and confidence
7. **Injury Prevention**: Consider history when suggesting intensity
8. **No Hallucination**: Don't make up data

TONE & STYLE:
- Professional but approachable
- Direct and actionable
- Evidence-based (cite metrics)
- Empowering and educational
- Responsive to psychological state

You know this athlete's physiology, history, patterns, and current state completely.
"""

        return prompt.strip()


class ProactiveCoachingEngine:
    """
    Generates unprompted coaching messages based on athlete state
    """

    @staticmethod
    def check_send_coaching_nudge(db: Session, user_id: int) -> Optional[Dict]:
        """
        Check if athlete should receive proactive coaching message.
        Sends if:
        - Readiness score is high (peak opportunity)
        - Injury risk is high (recovery recommendation)
        - Burnout risk detected (motivation boost)
        """
        try:
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            state = context.get("current_state", {})
            readiness = state.get("readiness", 0)
            injury_risk = state.get("injury_risk", 0)
            burnout_at_risk = context.get("burnout_risk", {}).get("at_risk", False)
            tsb = state.get("tsb", 0)
            motivation = context.get("psychological_state", {}).get("motivation", 0.7)

            nudge = None

            # Scenario 1: Peak readiness - great opportunity
            if readiness > 85 and tsb > 5:
                nudge = {
                    "type": "peak_opportunity",
                    "message": f"🏃 You're in great form! (Readiness: {readiness:.0f}/100). Consider a tempo run or race effort today.",
                    "priority": "high"
                }

            # Scenario 2: High injury risk - recommend recovery
            elif injury_risk > 70:
                nudge = {
                    "type": "injury_prevention",
                    "message": f"⚠️ Injury risk elevated ({injury_risk:.0f}/100). Take an easy day or rest to stay healthy.",
                    "priority": "critical"
                }

            # Scenario 3: Burnout detected - motivation boost
            elif burnout_at_risk and readiness < 50:
                reason = context.get("burnout_risk", {}).get("reason", "fatigue")
                nudge = {
                    "type": "motivation_boost",
                    "message": f"💪 I see you're struggling with {reason}. Remember your goals. Take it easy today.",
                    "priority": "high"
                }

            # Scenario 4: Low motivation
            elif motivation < 0.5:
                nudge = {
                    "type": "motivation_check",
                    "message": "💭 How are you feeling about training today? Let's discuss what's on your mind.",
                    "priority": "medium"
                }

            return nudge

        except Exception as e:
            logger.error(f"❌ Proactive coaching error: {e}")
            return None

    @staticmethod
    def generate_weekly_report(db: Session, user_id: int) -> Dict:
        """
        Generate automated weekly performance report.
        Sent every Friday with volume, CTL/ATL/TSB trends, and recommendations.
        """
        try:
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            if "error" in context:
                return {"success": False, "error": context["error"]}
            
            weekly = context.get("metrics", {}).get("weekly", {})
            state = context.get("current_state", {})
            athlete = context.get("athlete", {})

            report = f"""
📊 <b>Weekly Training Report</b>

<b>This Week's Stats:</b>
• Volume: {weekly.get('volume_km', 0):.1f} km
• Training Stress: {weekly.get('tss', 0):.0f} TSS
• Workouts: {weekly.get('workout_count', 0)}
• Avg HR: {weekly.get('avg_hr', 0):.0f} bpm

<b>Your Fitness Trends:</b>
• CTL (Fitness): {state.get('ctl', 0):.1f}
• ATL (Fatigue): {state.get('atl', 0):.1f}
• TSB (Recovery): {state.get('tsb', 0):.1f}
• Form Score: {state.get('form_score', 0):.1f}

<b>Next Week Preview:</b>
"""
            readiness = state.get("readiness", 0)
            if readiness > 70:
                report += "You're well-rested. Incorporate one tempo session mid-week.\n"
            elif readiness > 50:
                report += "You're recovering well. Continue base building with easy runs.\n"
            else:
                report += "You're fatigued. Focus on recovery and Zone 2 training this week.\n"

            report += f"""
Keep pushing! 💪
"""

            return {
                "success": True,
                "report": report,
                "type": "weekly_summary"
            }

        except Exception as e:
            logger.error(f"❌ Weekly report error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_daily_readiness_check(db: Session, user_id: int) -> Dict:
        """
        Generate daily readiness check message (sent at 6 AM).
        """
        try:
            context = ContextAssembler.assemble_coaching_context(db, user_id)
            state = context.get("current_state", {})
            readiness = state.get("readiness", 0)
            injury_risk = state.get("injury_risk", 0)
            athlete = context.get("athlete", {})

            if readiness > 80:
                message = f"🌅 Good morning! You're feeling fresh (Readiness: {readiness:.0f}/100). Today's a great day for a tempo run or long effort."
            elif readiness > 60:
                message = f"🌅 Good morning! You're ready for a solid workout (Readiness: {readiness:.0f}/100). Keep intensity moderate."
            else:
                message = f"🌅 Good morning! You need recovery today (Readiness: {readiness:.0f}/100). Easy pace only."

            if injury_risk > 70:
                message += f"\n⚠️ Stay extra careful today—injury risk is elevated ({injury_risk:.0f}/100)."

            return {
                "success": True,
                "message": message,
                "type": "daily_readiness",
                "readiness": readiness
            }

        except Exception as e:
            logger.error(f"❌ Daily readiness check error: {e}")
            return {"success": False, "error": str(e)}
