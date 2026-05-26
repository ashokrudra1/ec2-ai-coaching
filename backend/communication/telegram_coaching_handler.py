"""
Telegram Coaching Message Handler
Routes athlete messages to intelligent coach
Handles special commands and file uploads
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict
from sqlalchemy.orm import Session
from python_telegram_bot import Update
from python_telegram_bot.ext import ContextTypes
from python_telegram_bot.constants import ParseMode

from backend.database import SessionLocal
from backend.models import User
from backend.communication.intelligent_coach import IntelligentCoach, ProactiveCoachingEngine
from backend.communication.memory_pipeline import MemoryPipeline

logger = logging.getLogger(__name__)


class CoachingMessageHandler:
    """
    Handles incoming messages from Telegram athletes.
    Routes to IntelligentCoach, manages special commands.
    """

    # Available commands
    COMMANDS = {
        "/chat": "💬 Talk to your coach",
        "/status": "📊 View your fitness metrics",
        "/medical": "📋 Upload medical report",
        "/weekly": "📈 Get weekly summary",
        "/history": "📚 View past coaching tips",
        "/help": "❓ Show all commands"
    }

    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Main entry point: Route incoming messages to appropriate handler.
        """
        chat_id = str(update.effective_chat.id)
        user_message = update.message.text
        db = SessionLocal()

        try:
            # Get user
            user = db.query(User).filter_by(telegram_chat_id=chat_id).first()
            if not user:
                await update.message.reply_text(
                    "❌ User not found. Please /start to register.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Check subscription
            if not CoachingMessageHandler._check_subscription(user):
                await update.message.reply_text(
                    "⏰ Your subscription has expired. Please renew to continue coaching.\n"
                    "Reply /subscribe to view plans.",
                    parse_mode=ParseMode.HTML
                )
                return

            # Route by message type
            if user_message.startswith("/"):
                await CoachingMessageHandler._handle_command(
                    update, context, user, user_message
                )
            else:
                await CoachingMessageHandler._handle_coaching_message(
                    update, context, db, user, user_message
                )

        except Exception as e:
            logger.error(f"❌ Message handling error: {e}", exc_info=True)
            await update.message.reply_text(
                "⚠️ Something went wrong. Let me try again.",
                parse_mode=ParseMode.HTML
            )
        finally:
            db.close()

    @staticmethod
    async def _handle_coaching_message(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        db: Session,
        user: User,
        user_message: str
    ):
        """
        Handle regular coaching message.
        Generate personalized response using LLM.
        """
        try:
            # Show typing indicator
            await update.message.chat.send_action("typing")

            # Generate coaching response
            coach = IntelligentCoach(os.getenv("OPENAI_API_KEY"))
            response_dict = coach.generate_response(db, user.id, user_message)

            if not response_dict.get("success"):
                # Fallback message
                fallback = response_dict.get("fallback_message", 
                    "I'm analyzing your data. Let me get back to you shortly!")
                await update.message.reply_text(fallback, parse_mode=ParseMode.HTML)
                return

            coaching_response = response_dict.get("response", "")

            # Store in memory and extract learnings
            pipeline = MemoryPipeline(os.getenv("OPENAI_API_KEY"))
            pipeline.process_full_exchange(db, user.id, user_message, coaching_response)

            # Format and send response
            formatted_response = CoachingMessageHandler._format_coaching_response(
                coaching_response, 
                response_dict.get("context_summary", {})
            )

            await update.message.reply_text(
                formatted_response,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"✅ Coaching message sent to user {user.id}")

        except Exception as e:
            logger.error(f"❌ Coaching message error: {e}", exc_info=True)
            await update.message.reply_text(
                "⚠️ I encountered an error processing your message. Please try again.",
                parse_mode=ParseMode.HTML
            )

    @staticmethod
    async def _handle_command(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        user: User,
        command: str
    ):
        """
        Handle special commands like /status, /weekly, /help
        """
        db = SessionLocal()
        
        try:
            if command == "/help":
                await CoachingMessageHandler._cmd_help(update)

            elif command == "/status":
                await CoachingMessageHandler._cmd_status(update, user, db)

            elif command == "/weekly":
                await CoachingMessageHandler._cmd_weekly(update, user, db)

            elif command == "/history":
                await CoachingMessageHandler._cmd_history(update, user, db)

            elif command == "/medical":
                await update.message.reply_text(
                    "📋 <b>Upload Medical Report</b>\n\n"
                    "Send me a PDF file with your medical/health report.\n"
                    "I'll analyze it and update your profile automatically.",
                    parse_mode=ParseMode.HTML
                )

            elif command == "/chat":
                await update.message.reply_text(
                    "💬 <b>Talk to Your Coach</b>\n\n"
                    "Just send me a message! Ask about:\n"
                    "• Your current fitness level\n"
                    "• What workouts to do today\n"
                    "• How to improve your training\n"
                    "• Injury concerns\n"
                    "• Anything about running and training!",
                    parse_mode=ParseMode.HTML
                )

            else:
                await update.message.reply_text(
                    f"❓ Command '{command}' not recognized.\n"
                    "Use /help to see available commands.",
                    parse_mode=ParseMode.HTML
                )

        except Exception as e:
            logger.error(f"❌ Command handling error: {e}")
            await update.message.reply_text(
                "⚠️ Error processing command. Please try again.",
                parse_mode=ParseMode.HTML
            )
        finally:
            db.close()

    @staticmethod
    async def _cmd_help(update: Update):
        """Show help message with all commands"""
        help_text = "<b>📚 Available Commands:</b>\n\n"
        for cmd, description in CoachingMessageHandler.COMMANDS.items():
            help_text += f"<b>{cmd}</b> - {description}\n"
        
        help_text += "\n💬 Or just send me a message to chat with your coach!"
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    @staticmethod
    async def _cmd_status(update: Update, user: User, db: Session):
        """Show current fitness metrics"""
        from backend.training_system.coach_memory_engine import ContextAssembler

        try:
            context = ContextAssembler.assemble_coaching_context(db, user.id)
            state = context.get("current_state", {})
            metrics = context.get("metrics", {})

            status_text = f"""
<b>📊 Your Current Fitness Status</b>

<b>Training Load:</b>
• CTL (Fitness): {state.get('ctl', 0):.1f}
• ATL (Fatigue): {state.get('atl', 0):.1f}
• TSB (Recovery): {state.get('tsb', 0):.1f}

<b>Performance:</b>
• Readiness Score: {state.get('readiness', 0):.0f}/100
• Injury Risk: {state.get('injury_risk', 0):.0f}/100
• Form Score: {state.get('form_score', 0):.1f}

<b>This Week:</b>
• Volume: {metrics.get('weekly', {}).get('volume_km', 0):.1f} km
• TSS: {metrics.get('weekly', {}).get('tss', 0):.0f}
• Workouts: {metrics.get('weekly', {}).get('workout_count', 0)}

📈 Keep grinding! 💪
"""
            await update.message.reply_text(status_text, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.error(f"Status command error: {e}")
            await update.message.reply_text(
                "⚠️ Error fetching your status. Please try again.",
                parse_mode=ParseMode.HTML
            )

    @staticmethod
    async def _cmd_weekly(update: Update, user: User, db: Session):
        """Send weekly report"""
        try:
            engine = ProactiveCoachingEngine()
            result = engine.generate_weekly_report(db, user.id)

            if result.get("success"):
                await update.message.reply_text(
                    result.get("report", ""),
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text(
                    "⚠️ Could not generate report. Please try again.",
                    parse_mode=ParseMode.HTML
                )

        except Exception as e:
            logger.error(f"Weekly command error: {e}")
            await update.message.reply_text(
                "⚠️ Error generating weekly report.",
                parse_mode=ParseMode.HTML
            )

    @staticmethod
    async def _cmd_history(update: Update, user: User, db: Session):
        """Show recent coaching tips"""
        from backend.models import CoachMemory

        try:
            recent_tips = db.query(CoachMemory).filter(
                CoachMemory.user_id == user.id,
                CoachMemory.role == "assistant",
                CoachMemory.category == "coaching"
            ).order_by(CoachMemory.created_at.desc()).limit(5).all()

            if not recent_tips:
                await update.message.reply_text(
                    "📚 No coaching history yet. Start chatting with your coach!",
                    parse_mode=ParseMode.HTML
                )
                return

            history_text = "<b>📚 Recent Coaching Tips:</b>\n\n"
            for i, tip in enumerate(recent_tips, 1):
                history_text += f"<b>{i}.</b> {tip.content[:100]}...\n\n"

            await update.message.reply_text(history_text, parse_mode=ParseMode.HTML)

        except Exception as e:
            logger.error(f"History command error: {e}")
            await update.message.reply_text(
                "⚠️ Error fetching history.",
                parse_mode=ParseMode.HTML
            )

    @staticmethod
    def _check_subscription(user: User) -> bool:
        """
        Check if user has active subscription.
        """
        if not user.subscription_expiry:
            return False
        
        return user.subscription_expiry > datetime.now(timezone.utc)

    @staticmethod
    def _format_coaching_response(response: str, context_summary: Dict) -> str:
        """
        Format coaching response with metrics badges.
        """
        formatted = response

        # Add metrics summary if relevant
        readiness = context_summary.get("readiness", 0)
        injury_risk = context_summary.get("injury_risk", 0)

        if readiness:
            formatted += f"\n\n📈 <i>Readiness: {readiness:.0f}/100</i>"

        if injury_risk:
            formatted += f" | ⚠️ <i>Injury Risk: {injury_risk:.0f}/100</i>"

        return formatted.strip()


async def setup_coaching_handlers(application):
    """
    Register all coaching message handlers with Telegram bot.
    Call this during bot initialization.
    """
    from python_telegram_bot.ext import MessageHandler, filters

    # Regular messages
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, CoachingMessageHandler.handle_message)
    )

    # Commands
    application.add_handler(
        MessageHandler(filters.COMMAND, CoachingMessageHandler.handle_message)
    )

    logger.info("✅ Coaching message handlers registered")
