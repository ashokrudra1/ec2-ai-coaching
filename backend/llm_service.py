import os
import json
import logging
from datetime import datetime

from groq import Groq
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.models import CoachMemory

# =========================
# 🔧 INIT - GROQ SETUP
# =========================
load_dotenv()
_api_key = os.getenv("GROQ_API_KEY")
_default_model = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
client = Groq(api_key=_api_key)

logger = logging.getLogger(__name__)


# =========================
# 🤖 GENERATE COACH RESPONSE (GROQ)
# =========================
def generate_coach_response(context: dict) -> str:
    """
    Main LLM call for coaching response with strict length controls.
    Uses Groq's fast inference for real-time coaching.
    """

    # Enforce strict brevity, direct tips, and zero report-writing patterns
    system_message = context.get(
        "system_instructions",
        """You are an elite endurance running coach. Your tone is professional, direct, and highly focused.

Rules:
1. STRICT BREVITY: Keep your total response under 150 words (maximum 3 to 4 sentences).
2. NO FILLER: Skip conversational fluff, introductory greetings (e.g., "I hope you are doing well"), and warm sign-offs (e.g., "Onward and upward").
3. DIRECT ACTION: Immediately address the athlete's prompt using their metrics, and provide exactly ONE clear, practical next step.
4. Avoid generating long, structured outlines, multiple headings, or complete nutrition/recovery templates unless explicitly asked.
5. If data is missing → state it briefly, do not hallucinate.
"""
    )

    prompt = f"""
Athlete Name: {context.get('athlete_name')}

Performance Summary:
{context.get('performance')}

Recent Form:
{context.get('recent_form')}

Personal Bests:
{context.get('personal_bests')}

Fatigue Status: {context.get('fatigue')}
Fatigue Trend: {context.get('fatigue_trend')}

Goal:
{context.get('goal')}

Conversation History:
{context.get('history')}

Athlete's Message:
"{context.get('user_input')}"
"""

    try:
        response = client.chat.completions.create(
            model=_default_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300  # Groq parameter for response length
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.exception(f"❌ LLM response generation failed: {str(e)}")
        return "⚠️ I'm having trouble analyzing right now. Try again in a moment."


# =========================
# 🧠 MEMORY EXTRACTION (GROQ)
# =========================
def extract_and_save_memory(
    db: Session,
    user_id: int,
    user_input: str,
    ai_response: str
):
    """
    Extracts long-term useful insights and stores them using Groq
    """

    extraction_prompt = f"""
Analyze this athlete conversation:

User: "{user_input}"
Coach: "{ai_response}"

Extract ONE useful long-term insight if present, such as:
- injury
- goal
- preference
- limitation

Return ONLY JSON:
{{"insight": "short fact"}}

If nothing useful → return NONE
"""

    try:
        response = client.chat.completions.create(
            model=_default_model,
            messages=[
                {"role": "system", "content": "Extract structured athlete insights. Return only JSON."},
                {"role": "user", "content": extraction_prompt}
            ],
            temperature=0,
            max_tokens=200
        )

        result = response.choices[0].message.content.strip()

        if result.upper() == "NONE":
            return

        # Clean formatting (in case model wraps JSON)
        clean = result.replace("```json", "").replace("```", "").strip()

        if not clean.startswith("{"):
            return

        data = json.loads(clean)
        insight_text = data.get("insight")

        if insight_text:
            memory = CoachMemory(
                user_id=user_id,
                role="system",
                content=insight_text,
                created_at=datetime.utcnow()
            )

            db.add(memory)
            db.commit()

            logger.info(f"🧠 Memory saved: {insight_text}")

    except Exception as e:
        db.rollback()
        logger.exception(f"❌ Failed to extract memory: {str(e)}")


# =========================
# 🩺 MEDICAL PDF ANALYSER (GROQ)
# =========================
def process_medical_pdf_with_llm(raw_pdf_text: str, athlete_name: str) -> str:
    """
    Parses complex medical reports and summarizes critical coaching boundaries.
    Uses Groq for fast inference on large medical text.
    """
    system_instruction = (
        "You are an Elite Medical Analyst for Endurance Training. "
        "Your task is to read raw medical reports and extract ONLY items that directly affect sports training."
    )
    
    prompt = f"""
Analyze this raw medical text for athlete {athlete_name}.
Extract key indicators under these strict categories:
1. Cardiovascular Metrics (e.g., resting heart rate, ECG findings)
2. Musculoskeletal / Injury warning signs (e.g., knee, tendon, back reports)
3. Nutritional Deficiencies (e.g., low Iron, Ferritin, Vitamin D)
4. Active Restrictions (What the doctor explicitly said NOT to do, if any)

Be extremely clear and list only verified medical boundaries.

---
RAW REPORT TEXT:
{raw_pdf_text}
---
"""
    try:
        response = client.chat.completions.create(
            model=_default_model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception(f"❌ Medical report extraction failed: {str(e)}")
        return "No specific issues identified. Proceed with baseline thresholds."


# =========================
# 🔄 GROQ HEALTH CHECK
# =========================
def check_groq_health() -> dict:
    """
    Check if Groq API is accessible and working
    """
    try:
        response = client.chat.completions.create(
            model=_default_model,
            messages=[
                {"role": "user", "content": "ping"}
            ],
            temperature=0,
            max_tokens=10
        )
        return {
            "status": "healthy",
            "provider": "groq",
            "model": _default_model,
            "latency_ms": 0
        }
    except Exception as e:
        logger.error(f"❌ Groq health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "provider": "groq",
            "error": str(e)
        }
