"""
SIMPLE TELEGRAM BOT - Minimal, working version
Just registration - no complex coaching handlers
Run with: python start_bot.py
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode

from backend.database import SessionLocal
from backend.models import User

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# States
STATE_START, STATE_EMAIL, STATE_DOB, STATE_EXP, STATE_CONFIRM = range(5)


class SimpleRegistration:
    """Simple registration handler"""
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        
        logger.info(f"🚀 User /start: {user_id} ({user_name})")
        
        keyboard = [
            [InlineKeyboardButton("✅ Register", callback_data='reg_yes')],
            [InlineKeyboardButton("❌ Cancel", callback_data='reg_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"👋 Welcome to <b>Veda AI Coaching</b>, {user_name}!\n\n"
            f"Let's get started! 🏃‍♂️",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        context.user_data['user_id'] = user_id
        context.user_data['name'] = user_name
        return STATE_START
    
    @staticmethod
    async def reg_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """User clicks Register"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            text="📧 <b>What's your email?</b>\n\nExample: user@example.com",
            parse_mode=ParseMode.HTML
        )
        return STATE_EMAIL
    
    @staticmethod
    async def email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get email"""
        email = update.message.text.strip()
        
        if '@' not in email or '.' not in email:
            await update.message.reply_text("❌ Invalid email. Try again.")
            return STATE_EMAIL
        
        context.user_data['email'] = email
        
        await update.message.reply_text(
            "🎂 <b>Date of birth? (DD-MM-YYYY)</b>\n\nExample: 15-03-2010",
            parse_mode=ParseMode.HTML
        )
        return STATE_DOB
    
    @staticmethod
    async def dob_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get DOB"""
        dob_input = update.message.text.strip()
        
        try:
            dob = datetime.strptime(dob_input, "%d-%m-%Y").date()
            today = datetime.now(timezone.utc).date()
            
            if dob > today:
                await update.message.reply_text("❌ Date cannot be in future. Try again.")
                return STATE_DOB
            
            context.user_data['dob'] = dob
            
            keyboard = [
                [InlineKeyboardButton("🟢 Beginner", callback_data='exp_beginner')],
                [InlineKeyboardButton("🟡 Intermediate", callback_data='exp_int')],
                [InlineKeyboardButton("🔴 Advanced", callback_data='exp_adv')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🏃 <b>Experience level?</b>",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            return STATE_EXP
        
        except ValueError:
            await update.message.reply_text("❌ Invalid format. Use DD-MM-YYYY.")
            return STATE_DOB
    
    @staticmethod
    async def exp_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get experience level"""
        query = update.callback_query
        await query.answer()
        
        exp_map = {
            'exp_beginner': 'beginner',
            'exp_int': 'intermediate',
            'exp_adv': 'advanced'
        }
        
        context.user_data['experience'] = exp_map.get(query.data, 'beginner')
        
        # Show summary
        name = context.user_data['name']
        email = context.user_data['email']
        dob = context.user_data['dob']
        exp = context.user_data['experience'].capitalize()
        
        keyboard = [
            [InlineKeyboardButton("✅ Complete", callback_data='complete')],
            [InlineKeyboardButton("❌ Cancel", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = (
            f"📋 <b>Summary</b>\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"DOB: {dob}\n"
            f"Experience: {exp}\n\n"
            f"Correct?"
        )
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return STATE_CONFIRM
    
    @staticmethod
    async def complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete registration"""
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        try:
            user = User(
                telegram_chat_id=str(context.user_data['user_id']),
                name=context.user_data['name'],
                email=context.user_data['email'],
                dob=context.user_data['dob'],
                experience_level=context.user_data['experience'],
                timezone='Asia/Kolkata',
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            db.add(user)
            db.commit()
            
            logger.info(f"✅ User registered: {user.name} ({user.email})")
            
            await query.edit_message_text(
                "🎉 <b>Done!</b> Welcome to Veda AI Coaching! 🚀",
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"❌ DB error: {e}")
            await query.edit_message_text("❌ Error saving. Try again.")
        finally:
            db.close()
        
        return ConversationHandler.END
    
    @staticmethod
    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text("❌ Cancelled. Send /start again anytime.")
        return ConversationHandler.END


async def main():
    """Main"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not token:
        logger.error("❌ No TELEGRAM_BOT_TOKEN in .env")
        return
    
    logger.info(f"🤖 Starting bot with token: {token[:20]}...")
    
    app = Application.builder().token(token).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", SimpleRegistration.start)],
        states={
            STATE_START: [
                CallbackQueryHandler(SimpleRegistration.reg_yes, pattern="reg_yes"),
                CallbackQueryHandler(SimpleRegistration.cancel, pattern="reg_no"),
            ],
            STATE_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, SimpleRegistration.email_input)
            ],
            STATE_DOB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, SimpleRegistration.dob_input)
            ],
            STATE_EXP: [
                CallbackQueryHandler(SimpleRegistration.exp_select, pattern="^exp_")
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(SimpleRegistration.complete, pattern="complete"),
                CallbackQueryHandler(SimpleRegistration.cancel, pattern="cancel"),
            ],
        },
        fallbacks=[CommandHandler("cancel", SimpleRegistration.cancel)],
    )
    
    app.add_handler(conv_handler)
    
    logger.info("=" * 60)
    logger.info("✅ BOT READY - LISTENING FOR MESSAGES")
    logger.info("=" * 60)
    logger.info("Send /start to test!")
    logger.info("=" * 60)
    
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
