# backend/telegram_registration.py
"""
Telegram Bot User Registration Flow
First user interaction through Telegram /start command
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes, CallbackQueryHandler, CallbackContext
)
from backend.database import get_db
from backend.models import User
from backend.config.settings import settings

logger = logging.getLogger(__name__)

# Conversation states
STATE_START = 0
STATE_PHONE = 1
STATE_EMAIL = 2
STATE_NAME = 3
STATE_EXPERIENCE = 4
STATE_CONFIRM = 5

class TelegramUserRegistration:
    """Handle Telegram user registration and onboarding"""
    
    @staticmethod
    def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        return db.query(User).filter_by(telegram_chat_id=telegram_id).first()
    
    @staticmethod
    def create_user(db: Session, telegram_id: int, **kwargs) -> User:
        """Create new user from Telegram registration"""
        user = User(
            telegram_chat_id=telegram_id,
            name=kwargs.get('name', 'Unknown'),
            email=kwargs.get('email'),
            experience_level=kwargs.get('experience_level', 'beginner'),
            timezone=kwargs.get('timezone', 'Asia/Kolkata'),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            onboarding_step='registration_complete',
            **kwargs
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - first user interaction"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "User"
        
        logger.info(f"New user registration started: {user_id} ({user_name})")
        
        # Check if user already registered
        from backend.database import SessionLocal
        db = SessionLocal()
        
        try:
            existing_user = TelegramUserRegistration.get_user_by_telegram_id(db, user_id)
            if existing_user:
                await update.message.reply_text(
                    f"👋 Welcome back, {existing_user.name}!\n\n"
                    f"You're already registered in Veda AI Coaching.\n\n"
                    f"Commands:\n"
                    f"/help - Show all commands\n"
                    f"/profile - View your profile\n"
                    f"/stats - View your coaching stats\n"
                    f"/help - Get coaching tips"
                )
                return ConversationHandler.END
            
            # New user - start registration
            keyboard = [
                [InlineKeyboardButton("✅ Register", callback_data='register_confirm')],
                [InlineKeyboardButton("❌ Cancel", callback_data='register_cancel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 Welcome to Veda AI Coaching, {user_name}!\n\n"
                f"I'm your personal AI endurance coach. I'll help you:\n\n"
                f"✨ Optimize your training plans\n"
                f"📊 Analyze your performance\n"
                f"🎯 Achieve your fitness goals\n\n"
                f"Let's get started with registration!",
                reply_markup=reply_markup
            )
            
            context.user_data['telegram_id'] = user_id
            context.user_data['name'] = user_name
            
            return STATE_START
        finally:
            db.close()
    
    @staticmethod
    async def handle_register_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle registration confirmation"""
        query = update.callback_query
        await query.answer()
        
        # Ask for email
        await query.edit_message_text(
            text="📧 Great! What's your email address?\n\n"
            "We'll use this for notifications and account recovery.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Skip", callback_data='skip_email')]
            ])
        )
        
        return STATE_EMAIL
    
    @staticmethod
    async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle email input"""
        email = update.message.text
        
        if '@' not in email:
            await update.message.reply_text("❌ Please enter a valid email address")
            return STATE_EMAIL
        
        context.user_data['email'] = email
        
        # Ask for experience level
        keyboard = [
            [InlineKeyboardButton("🟢 Beginner", callback_data='exp_beginner')],
            [InlineKeyboardButton("🟡 Intermediate", callback_data='exp_intermediate')],
            [InlineKeyboardButton("🔴 Advanced", callback_data='exp_advanced')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text="🏃 What's your running experience level?\n\n"
            "This helps me customize your coaching!",
            reply_markup=reply_markup
        )
        
        return STATE_EXPERIENCE
    
    @staticmethod
    async def handle_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle experience level selection"""
        query = update.callback_query
        await query.answer()
        
        experience_map = {
            'exp_beginner': 'beginner',
            'exp_intermediate': 'intermediate',
            'exp_advanced': 'advanced'
        }
        
        experience = experience_map.get(query.data, 'beginner')
        context.user_data['experience_level'] = experience
        
        # Show confirmation
        user_name = context.user_data.get('name', 'User')
        email = context.user_data.get('email', 'Not provided')
        
        keyboard = [
            [InlineKeyboardButton("✅ Complete Registration", callback_data='complete_reg')],
            [InlineKeyboardButton("✏️ Edit", callback_data='edit_registration')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        confirmation_text = (
            f"📋 Registration Summary\n\n"
            f"Name: {user_name}\n"
            f"Email: {email}\n"
            f"Experience: {experience.capitalize()}\n\n"
            f"Is everything correct?"
        )
        
        await query.edit_message_text(
            text=confirmation_text,
            reply_markup=reply_markup
        )
        
        return STATE_CONFIRM
    
    @staticmethod
    async def handle_complete_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete user registration"""
        query = update.callback_query
        await query.answer()
        
        from backend.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Create user in database
            user = TelegramUserRegistration.create_user(
                db,
                telegram_id=context.user_data['telegram_id'],
                name=context.user_data['name'],
                email=context.user_data.get('email'),
                experience_level=context.user_data.get('experience_level', 'beginner'),
                timezone='Asia/Kolkata'
            )
            
            logger.info(f"User registered successfully: {user.id} ({user.name})")
            
            # Send welcome message
            keyboard = [
                [InlineKeyboardButton("📊 Connect Strava", callback_data='connect_strava')],
                [InlineKeyboardButton("📝 View Profile", callback_data='view_profile')],
                [InlineKeyboardButton("❓ Help", callback_data='show_help')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=(
                    f"🎉 Registration Complete!\n\n"
                    f"Welcome to Veda AI Coaching, {user.name}!\n\n"
                    f"Your account is ready. Now let's connect your Strava account "
                    f"to start your personalized coaching journey.\n\n"
                    f"What would you like to do next?"
                ),
                reply_markup=reply_markup
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            await query.edit_message_text(
                text="❌ Error during registration. Please try again later."
            )
            return ConversationHandler.END
        finally:
            db.close()
    
    @staticmethod
    async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel registration"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            text="❌ Registration cancelled.\n\n"
            "Feel free to start again with /start when you're ready!"
        )
        
        return ConversationHandler.END


def setup_telegram_registration(app: Application):
    """Setup Telegram registration handlers"""
    
    # Registration conversation handler
    registration_handler = ConversationHandler(
        entry_points=[CommandHandler('start', TelegramUserRegistration.handle_start)],
        states={
            STATE_START: [
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_register_confirm,
                    pattern='register_confirm'
                ),
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_cancel,
                    pattern='register_cancel'
                )
            ],
            STATE_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, TelegramUserRegistration.handle_email),
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_experience,
                    pattern='skip_email'
                )
            ],
            STATE_EXPERIENCE: [
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_experience,
                    pattern='^exp_'
                )
            ],
            STATE_CONFIRM: [
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_complete_registration,
                    pattern='complete_reg'
                ),
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_cancel,
                    pattern='edit_registration'
                )
            ]
        },
        fallbacks=[CommandHandler('cancel', TelegramUserRegistration.handle_cancel)]
    )
    
    # Add handler to application
    app.add_handler(registration_handler)
    
    logger.info("Telegram registration handlers configured")
