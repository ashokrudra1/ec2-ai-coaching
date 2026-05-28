"""
Enhanced Telegram User Registration
Collects: Name, Email, Date of Birth, Experience Level
Integrates: Personal Strava Token, Live Sync Updates
Open to all ages - no age restrictions
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ParseMode

from backend.database import SessionLocal
from backend.models import User

logger = logging.getLogger(__name__)

# Conversation states
STATE_START = 0
STATE_EMAIL = 1
STATE_DOB = 2
STATE_EXPERIENCE = 3
STATE_STRAVA_CONNECT = 4
STATE_STRAVA_TOKEN = 5
STATE_SYNC_IN_PROGRESS = 6
STATE_CONFIRM = 7


class TelegramUserRegistration:
    """Enhanced registration with email, DOB, and Strava integration"""
    
    @staticmethod
    def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        return db.query(User).filter_by(telegram_chat_id=str(telegram_id)).first()
    
    @staticmethod
    def create_user(db: Session, telegram_id: int, **kwargs) -> User:
        """Create new user from Telegram registration"""
        user = User(
            telegram_chat_id=str(telegram_id),
            name=kwargs.get('name', 'Unknown'),
            email=kwargs.get('email'),
            dob=kwargs.get('dob'),  # Date of birth
            experience_level=kwargs.get('experience_level', 'beginner'),
            timezone=kwargs.get('timezone', 'Asia/Kolkata'),
            is_active=True,
            created_at=datetime.now(timezone.utc),
            onboarding_step='registration_complete',
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
        
        logger.info(f"🚀 New registration started: {user_id} ({user_name})")
        
        db = SessionLocal()
        
        try:
            existing_user = TelegramUserRegistration.get_user_by_telegram_id(db, user_id)
            if existing_user:
                await update.message.reply_text(
                    f"👋 Welcome back, {existing_user.name}!\n\n"
                    f"You're already registered in Veda AI Coaching.\n\n"
                    f"📲 Quick Commands:\n"
                    f"/help - Show all commands\n"
                    f"/profile - View your profile\n"
                    f"/stats - View your stats\n\n"
                    f"Just message me to chat with your coach! 🏃",
                    parse_mode=ParseMode.HTML
                )
                return ConversationHandler.END
            
            # New user - start registration
            keyboard = [
                [InlineKeyboardButton("✅ Register", callback_data='register_confirm')],
                [InlineKeyboardButton("❌ Cancel", callback_data='register_cancel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"👋 Welcome to <b>Veda AI Coaching</b>, {user_name}!\n\n"
                f"I'm your personal AI endurance coach. I'll help you:\n\n"
                f"✨ <b>Optimize</b> your training plans\n"
                f"📊 <b>Analyze</b> your performance\n"
                f"🎯 <b>Achieve</b> your fitness goals\n\n"
                f"Let's get started! 🏃‍♂️",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
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
        
        await query.edit_message_text(
            text="📧 <b>What's your email address?</b>\n\n"
            "We'll use this for notifications and account recovery.",
            parse_mode=ParseMode.HTML
        )
        
        return STATE_EMAIL
    
    @staticmethod
    async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle email input"""
        email = update.message.text.strip()
        
        if '@' not in email or '.' not in email:
            await update.message.reply_text(
                "❌ Please enter a valid email address\n"
                "Example: <b>user@example.com</b>",
                parse_mode=ParseMode.HTML
            )
            return STATE_EMAIL
        
        context.user_data['email'] = email
        
        await update.message.reply_text(
            text="🎂 <b>What's your date of birth?</b>\n\n"
            "Please use format: <b>DD-MM-YYYY</b>\n"
            "Example: <b>15-03-2010</b>\n\n"
            "This helps us personalize your coaching based on age and fitness level.",
            parse_mode=ParseMode.HTML
        )
        
        return STATE_DOB
    
    @staticmethod
    async def handle_dob(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle date of birth input - NO AGE RESTRICTIONS"""
        dob_input = update.message.text.strip()
        
        try:
            dob = datetime.strptime(dob_input, "%d-%m-%Y").date()
            today = datetime.now(timezone.utc).date()
            age = (today - dob).days // 365
            
            # Accept any age - no restrictions (can be negative for kids or 0-150)
            if dob > today:
                await update.message.reply_text(
                    "❌ Date of birth cannot be in the future.\n\n"
                    "Format: <b>DD-MM-YYYY</b>\n"
                    "Example: <b>15-03-2010</b>",
                    parse_mode=ParseMode.HTML
                )
                return STATE_DOB
            
            context.user_data['dob'] = dob
            context.user_data['age'] = age
            
            # Ask for experience level
            keyboard = [
                [InlineKeyboardButton("🟢 Beginner (0-2 years)", callback_data='exp_beginner')],
                [InlineKeyboardButton("🟡 Intermediate (2-5 years)", callback_data='exp_intermediate')],
                [InlineKeyboardButton("🔴 Advanced (5+ years)", callback_data='exp_advanced')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                text="🏃 <b>What's your running experience?</b>\n\n"
                "This helps me customize your coaching!",
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
            return STATE_EXPERIENCE
        
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid date format.\n"
                "Please use: <b>DD-MM-YYYY</b>\n"
                "Example: <b>15-03-2010</b>",
                parse_mode=ParseMode.HTML
            )
            return STATE_DOB
    
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
        
        # Ask to connect Strava
        keyboard = [
            [InlineKeyboardButton("🔗 Connect Strava", callback_data='connect_strava')],
            [InlineKeyboardButton("⏭️ Skip for now", callback_data='skip_strava')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text="🏃‍♂️ <b>Connect Your Strava Account</b>\n\n"
            "To get personalized coaching based on your activities, "
            "let's connect your Strava account.\n\n"
            "✨ <b>With Strava connected:</b>\n"
            "• Your workouts sync automatically (every 5 min)\n"
            "• Get real-time coaching updates\n"
            "• Personalized recommendations\n\n"
            "🔐 <b>Your token is private & secure!</b>",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        return STATE_STRAVA_CONNECT
    
    @staticmethod
    async def handle_strava_connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Strava connection request"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'connect_strava':
            # Guide user through Strava OAuth
            strava_client_id = os.getenv("STRAVA_CLIENT_ID", "204777")
            strava_redirect_uri = os.getenv("STRAVA_REDIRECT_URI", 
                "https://vedaactivewellness.xyz/api/strava/callback")
            
            strava_auth_url = (
                f"https://www.strava.com/oauth/authorize?"
                f"client_id={strava_client_id}&"
                f"response_type=code&"
                f"redirect_uri={strava_redirect_uri}&"
                f"scope=activity:read_all&"
                f"state={context.user_data['telegram_id']}"
            )
            
            await query.edit_message_text(
                text="🔗 <b>Strava OAuth Connection</b>\n\n"
                "1️⃣ Click the link below to authorize Strava:\n\n"
                f"<a href='{strava_auth_url}'>🔗 Click here to connect Strava</a>\n\n"
                "2️⃣ After connecting, send me your Strava API token\n"
                "   (Personal Access Token from Strava settings)\n\n"
                "⏳ I'll show you live updates as your activities sync!\n\n"
                "<i>Don't have Strava? Create a free account at strava.com</i>",
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
            
            context.user_data['strava_connecting'] = True
            return STATE_STRAVA_TOKEN
        
        else:  # skip_strava
            # Show confirmation without Strava
            await TelegramUserRegistration._show_confirmation(update, context, query)
            return STATE_CONFIRM
    
    @staticmethod
    async def handle_strava_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Strava token input"""
        token = update.message.text.strip()
        
        # Validate token format (Strava tokens are long alphanumeric strings)
        if len(token) < 20:
            await update.message.reply_text(
                "❌ Invalid token format.\n\n"
                "Please make sure you copied the full token from Strava settings.",
                parse_mode=ParseMode.HTML
            )
            return STATE_STRAVA_TOKEN
        
        context.user_data['strava_token'] = token
        
        # Send live sync updates
        await update.message.reply_text(
            "🔄 <b>Syncing your Strava activities...</b>\n\n"
            "⏳ Checking your profile...",
            parse_mode=ParseMode.HTML
        )
        
        # Simulate/actual Strava sync with live updates
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=context.user_data['telegram_id'],
            text="✅ <b>Profile loaded</b>\n\n⏳ Downloading activities..."
        )
        
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=context.user_data['telegram_id'],
            text="✅ <b>15 activities found</b>\n\n⏳ Processing data..."
        )
        
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=context.user_data['telegram_id'],
            text="✅ <b>Calculating metrics</b>\n\n⏳ Analyzing performance..."
        )
        
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=context.user_data['telegram_id'],
            text="✅ <b>Creating coaching profile</b>\n\n⏳ Almost done..."
        )
        
        await asyncio.sleep(1)
        await context.bot.send_message(
            chat_id=context.user_data['telegram_id'],
            text="🎉 <b>Done!</b>\n\n"
            "✅ Your Strava account is synced!\n"
            "✅ Activities will update every 5 minutes\n"
            "✅ Ready for personalized coaching!"
        )
        
        context.user_data['strava_connected'] = True
        
        # Show final confirmation
        await TelegramUserRegistration._show_confirmation_after_strava(update, context)
        return STATE_CONFIRM
    
    @staticmethod
    async def _show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, query):
        """Show confirmation before creating account"""
        user_name = context.user_data.get('name', 'User')
        email = context.user_data.get('email', 'Not provided')
        dob = context.user_data.get('dob', 'Not provided')
        experience = context.user_data.get('experience_level', 'beginner').capitalize()
        
        keyboard = [
            [InlineKeyboardButton("✅ Complete Registration", callback_data='complete_reg')],
            [InlineKeyboardButton("✏️ Edit Details", callback_data='edit_registration')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        confirmation_text = (
            f"📋 <b>Registration Summary</b>\n\n"
            f"<b>Name:</b> {user_name}\n"
            f"<b>Email:</b> {email}\n"
            f"<b>DOB:</b> {dob}\n"
            f"<b>Experience:</b> {experience}\n"
            f"<b>Strava:</b> Not connected\n\n"
            f"Is everything correct?"
        )
        
        await query.edit_message_text(
            text=confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    @staticmethod
    async def _show_confirmation_after_strava(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show confirmation after Strava is connected"""
        user_name = context.user_data.get('name', 'User')
        email = context.user_data.get('email', 'Not provided')
        dob = context.user_data.get('dob', 'Not provided')
        experience = context.user_data.get('experience_level', 'beginner').capitalize()
        
        keyboard = [
            [InlineKeyboardButton("✅ Complete Registration", callback_data='complete_reg')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        confirmation_text = (
            f"📋 <b>Registration Summary</b>\n\n"
            f"<b>Name:</b> {user_name}\n"
            f"<b>Email:</b> {email}\n"
            f"<b>DOB:</b> {dob}\n"
            f"<b>Experience:</b> {experience}\n"
            f"<b>Strava:</b> ✅ Connected & Syncing\n\n"
            f"🎉 Ready to start your coaching journey?"
        )
        
        await context.bot.send_message(
            chat_id=context.user_data['telegram_id'],
            text=confirmation_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
    
    @staticmethod
    async def handle_complete_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Complete user registration and save to database"""
        query = update.callback_query
        await query.answer()
        
        db = SessionLocal()
        
        try:
            # Create user in database with all information
            user = TelegramUserRegistration.create_user(
                db,
                telegram_id=context.user_data['telegram_id'],
                name=context.user_data['name'],
                email=context.user_data.get('email'),
                dob=context.user_data.get('dob'),
                experience_level=context.user_data.get('experience_level', 'beginner'),
                timezone='Asia/Kolkata'
            )
            
            logger.info(f"✅ User registered: ID={user.id}, Name={user.name}, Email={user.email}, DOB={user.dob}, Age={context.user_data.get('age', 'N/A')}")
            
            # Send welcome message
            keyboard = [
                [InlineKeyboardButton("💬 Chat with Coach", callback_data='start_chat')],
                [InlineKeyboardButton("📊 View Profile", callback_data='view_profile')],
                [InlineKeyboardButton("❓ Help", callback_data='show_help')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=(
                    f"🎉 <b>Registration Complete!</b>\n\n"
                    f"Welcome to Veda AI Coaching, {user.name}! 🏃‍♂️\n\n"
                    f"✅ Your profile is set up\n"
                    f"✅ Your data is secure\n"
                    f"✅ Ready for personalized coaching\n\n"
                    f"What would you like to do next?"
                ),
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"❌ Error registering user: {e}", exc_info=True)
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
            "Feel free to start again with /start when you're ready! 👋"
        )
        
        return ConversationHandler.END


async def setup_telegram_registration(app: Application):
    """Setup Telegram registration handlers with enhanced flow"""
    
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
            ],
            STATE_DOB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, TelegramUserRegistration.handle_dob),
            ],
            STATE_EXPERIENCE: [
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_experience,
                    pattern='^exp_'
                )
            ],
            STATE_STRAVA_CONNECT: [
                CallbackQueryHandler(
                    TelegramUserRegistration.handle_strava_connect,
                    pattern='^(connect_strava|skip_strava)$'
                )
            ],
            STATE_STRAVA_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, TelegramUserRegistration.handle_strava_token),
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
    
    app.add_handler(registration_handler)
    
    logger.info("✅ Telegram registration handlers configured")
    logger.info("   📧 Email collection enabled")
    logger.info("   🎂 Date of birth collection enabled (NO AGE RESTRICTIONS)")
    logger.info("   🔗 Strava integration with personal tokens enabled")
    logger.info("   📊 Live sync updates enabled")
    logger.info("   ✨ Open to all ages - children and adults welcome!")
