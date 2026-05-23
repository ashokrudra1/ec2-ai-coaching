# backend/tasks/sync_tasks.py
import os
import logging
import asyncio
import httpx
from dateutil import parser
from sqlalchemy.exc import IntegrityError

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import User, Activity, DailyReadiness
from backend.notifications import (
    send_telegram_message,
    send_telegram_buttons,
    send_telegram_url_button
)
from backend.orchestration.coach_service import CoachService
from backend.plan_generator import generate_training_plan
from backend.pdf_utils import extract_text_from_pdf_bytes
from backend.llm_service import process_medical_pdf_with_llm
from backend.analytics import calculate_activity_tss, update_user_fitness_metrics

logger = logging.getLogger(__name__)

EMERGENCY_TRIGGERS = ["chest pain", "tightness in chest", "shortness of breath", "severe dizziness", "passed out", "unconscious", "heart racing abnormally"]

@celery_app.task(name="backend.tasks.sync_tasks.trigger_onboarding_backfill")
def trigger_onboarding_backfill(user_id: int):
    """
    Executes intensive historical backfill safely inside a worker process 
    without blockages or namespace collisions.
    """
    from backend.strava_manager import strava_manager
    logger.info(f"🏁 Starting onboarding background backfill for User ID {user_id}")
    return asyncio.run(strava_manager.backfill(user_id))


@celery_app.task(name="backend.tasks.sync_tasks.trigger_periodic_sync")
def trigger_periodic_sync():
    """Celery Beat entrypoint to safely synchronize recent training logs."""
    from backend.strava_manager import strava_manager
    logger.info("🔄 Initializing periodic activity synchronization loop...")
    asyncio.run(strava_manager.sync_recent())


@celery_app.task(name="backend.tasks.sync_tasks.trigger_durable_webhook_handler")
def trigger_durable_webhook_handler(body: dict):
    """
    SaaS-Grade Durable Webhook Handler. Processes raw Telegram JSON 
    payloads asynchronously inside Celery.
    """
    db = SessionLocal()
    try:
        logger.info({"event": "webhook_processing_started", "payload_keys": list(body.keys())})

        # ==========================================
        # 🔘 HANDLE BUTTON CLICKS (CALLBACK QUERIES)
        # ==========================================
        if "callback_query" in body:
            chat_id = str(body["callback_query"]["message"]["chat"]["id"])
            data = body["callback_query"]["data"]

            logger.info({"event": "button_clicked", "chat_id": chat_id, "callback_data": data})
            user = db.query(User).filter_by(telegram_chat_id=chat_id).first()

            if not user:
                send_telegram_message("⚠️ Registration mismatch. Send /start to begin.", chat_id)
                return

            if data == "Start Training":
                send_telegram_message("🏁 Let's begin your training journey! Keep consistency high.", chat_id)

            elif data == "View Plan":
                plan = generate_training_plan(db, user.id, user.target_goal or "general")
                send_telegram_message(plan, chat_id)

            elif data == "Sync Activities":
                send_telegram_message("🔄 Sync task enqueued safely into Celery worker processing grids...", chat_id)
                trigger_periodic_sync.delay() # Non-blocking execution pattern

            elif data.startswith("PERSONA:"):
                selected_persona = data.split(":")[1]
                user.coach_persona = selected_persona
                db.commit()

                persona_names = {
                    "veda": "Coach Veda (Olympic Scientist)",
                    "dev": "Captain Dev (Drill Sergeant)",
                    "priya": "Coach Priya (Supportive Guide)"
                }
                send_telegram_message(f"👤 *Coach Persona Updated:* Active style set to *{persona_names[selected_persona]}*.", chat_id)

            elif data.startswith("RPE:"):
                latest_activity = (
                    db.query(Activity)
                    .filter_by(user_id=user.id)
                    .order_by(Activity.start_date_utc.desc())
                    .first()
                )

                if latest_activity:
                    if "1-3" in data: rpe_val = 3
                    elif "4-6" in data: rpe_val = 5
                    elif "7-8" in data: rpe_val = 8
                    else: rpe_val = 10

                    latest_activity.perceived_exertion_rpe = rpe_val
                    latest_activity.training_stress_score_tss = calculate_activity_tss(latest_activity, user)
                    db.commit()

                    update_user_fitness_metrics(db, user.id, latest_activity.training_stress_score_tss)

                    send_telegram_message(
                        f"📝 *Effort Recorded:* Subjective score of {rpe_val}/10 applied.\n\n"
                        f"Current Form (TSB): *{user.tsb}* | Fatigue (ATL): *{user.atl}*",
                        chat_id
                    )
                else:
                    send_telegram_message("⚠️ No recent runs found to apply effort score.", chat_id)
            return

        # ==========================================
        # 📂 FILE AND PDF REPORTS
        # ==========================================
        message_data = body.get("message", {})
        chat_id = str(message_data.get("chat", {}).get("id"))
        user = db.query(User).filter_by(telegram_chat_id=chat_id).first()

        if "document" in message_data:
            if not user:
                send_telegram_message("👋 Welcome to Veda AI! Please register before uploading documents.", chat_id)
                return

            doc = message_data["document"]
            mime_type = doc.get("mime_type", "")
            file_name = doc.get("file_name", "document.pdf")

            if "pdf" not in mime_type.lower() and not file_name.lower().endswith(".pdf"):
                send_telegram_message("❌ Please upload a valid PDF document.", chat_id)
                return

            send_telegram_message("⏳ Reading and extracting your medical/fitness report. One moment...", chat_id)
            file_id = doc["file_id"]

            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            with httpx.Client() as client_http:
                info_res = client_http.get(f"https://api.telegram.org/bot{telegram_token}/getFile?file_id={file_id}")
                if info_res.status_code != 200:
                    send_telegram_message("❌ Failed to retrieve file info from Telegram.", chat_id)
                    return

                file_path = info_res.json().get("result", {}).get("file_path")
                file_url = f"https://api.telegram.org/file/bot{telegram_token}/{file_path}"
                file_res = client_http.get(file_url)

                if file_res.status_code != 200:
                    send_telegram_message("❌ Failed to retrieve file from Telegram servers.", chat_id)
                    return

                pdf_text = extract_text_from_pdf_bytes(file_res.content)
                if not pdf_text:
                    send_telegram_message("❌ Could not extract text from this PDF.", chat_id)
                    return

                extracted_insights = process_medical_pdf_with_llm(pdf_text, user.name)

                try:
                    user.medical_insights = extracted_insights
                    db.commit()
                except Exception:
                    db.rollback()
                    logger.exception("❌ Failed to commit medical insights")
                    send_telegram_message("❌ Database write failure. Please try again.", chat_id)
                    return

                send_telegram_message(
                    f"✅ **Medical boundaries successfully updated!**\n\nActive limits stored:\n{extracted_insights}",
                    chat_id
                )
                return

        # ==========================================
        # 💬 TEXT CHATS AND ONBOARDING
        # ==========================================
        if "text" not in message_data:
            return

        text = message_data.get("text", "").strip()

        text_lower = text.lower()
        if any(trigger in text_lower for trigger in EMERGENCY_TRIGGERS):
            emergency_instructions = (
                "🚨 *CRITICAL SAFETY WARNING:*\n"
                "You have reported symptoms indicating acute cardiorespiratory or muscular distress. "
                "Coaching operations are **SUSPENDED**. Please stop exercising immediately, do not wait for analysis, "
                "and contact emergency services or consult a cardiologist right away."
            )
            send_telegram_message(emergency_instructions, chat_id)
            return

        if not user:
            user = User(name="Athlete", telegram_chat_id=chat_id, onboarding_step=0)
            try:
                db.add(user)
                db.commit()
            except IntegrityError:
                db.rollback()
                user = db.query(User).filter_by(telegram_chat_id=chat_id).first()

            send_telegram_message("Welcome to Veda AI! 🏃‍♂️ I'm your coach.\n\nWhat should I call you?", chat_id)
            return

        logger.info({"event": "text_message_received", "chat_id": chat_id, "step": user.onboarding_step})

        if text.startswith("/start"):
            step = int(user.onboarding_step)
            if step == 0:
                send_telegram_message("Welcome! What should I call you?", chat_id)
            elif step == 1:
                send_telegram_message(f"Hi {user.name}, what is your DOB? (YYYY-MM-DD)", chat_id)
            elif step == 2:
                send_telegram_message("What is your fitness goal?", chat_id)
            elif step == 3:
                send_telegram_message("Tell me about your running background.", chat_id)
            else:
                send_telegram_message(f"Welcome back {user.name}! 👋 Ask me anything about your training.", chat_id)
            return

        if user.onboarding_step == 0:
            user.name = text
            user.onboarding_step = 1
            db.commit()
            send_telegram_message(f"Nice to meet you {user.name}! 👋\n\nWhat is your DOB? (YYYY-MM-DD)", chat_id)
            return

        elif user.onboarding_step == 1:
            try:
                user.dob = parser.parse(text).date()
                user.onboarding_step = 2
                db.commit()
                send_telegram_message("Great! 🎯 What is your fitness goal?", chat_id)
            except Exception:
                send_telegram_message("⚠️ Please enter a valid DOB (e.g. 1990-05-21)", chat_id)
            return

        elif user.onboarding_step == 2:
            user.target_goal = text
            user.onboarding_step = 3
            db.commit()
            send_telegram_message("Got it! ⚡ Tell me about your background (e.g. 20km/week)", chat_id)
            return

        elif user.onboarding_step == 3:
            user.background_bio = text
            user.onboarding_step = 4
            db.commit()

            from backend.strava_auth import generate_auth_link
            auth_url = generate_auth_link(str(chat_id))

            disclaimer = (
                "⚖️ *Legal Disclaimer:*\n"
                "Veda OS provides training analysis and fitness load guidance based on mathematical sports-science models. "
                "It is not a medical diagnostic tool. If you experience persistent pain, chest discomfort, or extreme fatigue, "
                "pause your training and consult a medical professional immediately.\n\n"
            )

            send_telegram_message(disclaimer, chat_id)
            send_telegram_url_button(
                f"🎉 You're all set, {user.name}!\n\n🧡 Connect your Strava account here:",
                "Connect Strava",
                auth_url,
                chat_id
            )
            return

        else:
            send_telegram_message("🤖 *Veda Coach is analyzing your metrics...*", chat_id)
            response = CoachService.generate(db, user.id, user_input=text)
            send_telegram_message(response, chat_id)

    except Exception as e:
        db.rollback()
        logger.error({"event": "durable_webhook_processing_failed", "error": str(e)}, exc_info=True)
    finally:
        db.close()
