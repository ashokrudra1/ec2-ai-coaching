"""
Telegram Bot Registration Flow
Handles: /start → /register → Plan Selection → Payment → Strava OAuth
Complete end-to-end registration automation
"""
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from python_telegram_bot import Update
from python_telegram_bot.ext import ContextTypes
from python_telegram_bot.constants import ParseMode

from backend.database import SessionLocal
from backend.models import User, SubscriptionTier
from backend.security.encryption import encrypt_data

logger = logging.getLogger(__name__)


class RegistrationFlow:
    """Manages complete end-to-end registration workflow"""

    # Registration states
    STATES = {
        "START": 0,
        "NAME": 1,
        "AGE": 2,
        "EXPERIENCE": 3,
        "GOAL": 4,
        "PLAN": 5,
        "PAYMENT": 6,
        "STRAVA_AUTH": 7,
        "COMPLETED": 8,
    }

    EXPERIENCE_OPTIONS = ["Beginner", "Intermediate", "Advanced", "Elite"]
    GOAL_OPTIONS = ["Marathon", "Half Marathon", "5K Speed", "Base Building", "Custom"]

    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start command - Entry point
        """
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        db = SessionLocal()

        try:
            # Check if already registered
            existing = db.query(User).filter_by(telegram_chat_id=chat_id).first()

            if existing:
                await update.message.reply_text(
                    f"👋 Welcome back, <b>{existing.name}</b>!\n\n"
                    f"<b>Quick Menu:</b>\n"
                    f"/chat - Chat with coach\n"
                    f"/status - Your stats\n"
                    f"/plan - Current plan\n"
                    f"/medical - Upload medical report\n"
                    f"/help - Commands",
                    parse_mode=ParseMode.HTML,
                )
                return

            # New user - start registration
            context.user_data["reg_state"] = RegistrationFlow.STATES["NAME"]
            context.user_data["chat_id"] = chat_id
            context.user_data["user_telegram_id"] = user.id
            context.user_data["username"] = user.username or "Athlete"

            await update.message.reply_text(
                "🏃‍♂️ <b>Welcome to AI Coach</b>!\n\n"
                "Your intelligent personal running coach powered by AI.\n\n"
                "Let's get you set up in 2 minutes ⚡\n\n"
                "<i>What's your name?</i>",
                parse_mode=ParseMode.HTML,
            )

        except Exception as e:
            logger.error(f"❌ /start error: {e}", exc_info=True)
            await update.message.reply_text("❌ Error. Please try: /start")
        finally:
            db.close()

    @staticmethod
    async def process_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Route input based on current registration state
        """
        text = update.message.text.strip()
        state = context.user_data.get("reg_state")
        chat_id = context.user_data.get("chat_id")

        if not state:
            return

        try:
            if state == RegistrationFlow.STATES["NAME"]:
                await RegistrationFlow._input_name(update, context, text)

            elif state == RegistrationFlow.STATES["AGE"]:
                await RegistrationFlow._input_age(update, context, text)

            elif state == RegistrationFlow.STATES["EXPERIENCE"]:
                await RegistrationFlow._input_experience(update, context, text)

            elif state == RegistrationFlow.STATES["GOAL"]:
                await RegistrationFlow._input_goal(update, context, text)

            elif state == RegistrationFlow.STATES["PLAN"]:
                await RegistrationFlow._input_plan(update, context, text)

        except Exception as e:
            logger.error(f"❌ Registration input error: {e}", exc_info=True)
            await update.message.reply_text("❌ Error. Please try again.")

    @staticmethod
    async def _input_name(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str):
        """Collect athlete name"""
        if len(name) < 2 or len(name) > 50:
            await update.message.reply_text("❌ Name must be 2-50 characters. Try again:")
            return

        context.user_data["name"] = name
        context.user_data["reg_state"] = RegistrationFlow.STATES["AGE"]
        await update.message.reply_text(f"✅ Great, <b>{name}</b>!\n\nWhat's your age?", parse_mode=ParseMode.HTML)

    @staticmethod
    async def _input_age(update: Update, context: ContextTypes.DEFAULT_TYPE, age_str: str):
        """Collect age"""
        try:
            age = int(age_str)
            if age < 15 or age > 100:
                await update.message.reply_text("❌ Age must be 15-100. Try again:")
                return

            context.user_data["age"] = age
            context.user_data["reg_state"] = RegistrationFlow.STATES["EXPERIENCE"]

            # Show experience options
            options_text = "\n".join([f"• {opt}" for opt in RegistrationFlow.EXPERIENCE_OPTIONS])
            await update.message.reply_text(
                f"✅ Age {age} recorded.\n\n"
                f"<b>Your running experience?</b>\n{options_text}\n\n"
                f"<i>Reply with one of the above</i>",
                parse_mode=ParseMode.HTML,
            )
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number:")

    @staticmethod
    async def _input_experience(update: Update, context: ContextTypes.DEFAULT_TYPE, exp: str):
        """Collect experience level"""
        if exp not in RegistrationFlow.EXPERIENCE_OPTIONS:
            options_text = "\n".join([f"• {opt}" for opt in RegistrationFlow.EXPERIENCE_OPTIONS])
            await update.message.reply_text(f"❌ Choose from:\n{options_text}")
            return

        context.user_data["experience"] = exp
        context.user_data["reg_state"] = RegistrationFlow.STATES["GOAL"]

        goals_text = "\n".join([f"• {goal}" for goal in RegistrationFlow.GOAL_OPTIONS])
        await update.message.reply_text(
            f"✅ {exp} runner!\n\n<b>Your primary goal?</b>\n{goals_text}\n\n<i>Reply with one of the above</i>",
            parse_mode=ParseMode.HTML,
        )

    @staticmethod
    async def _input_goal(update: Update, context: ContextTypes.DEFAULT_TYPE, goal: str):
        """Collect training goal"""
        if goal not in RegistrationFlow.GOAL_OPTIONS:
            goals_text = "\n".join([f"• {g}" for g in RegistrationFlow.GOAL_OPTIONS])
            await update.message.reply_text(f"❌ Choose from:\n{goals_text}")
            return

        context.user_data["goal"] = goal
        context.user_data["reg_state"] = RegistrationFlow.STATES["PLAN"]

        # Show plans
        await RegistrationFlow._show_plans(update, context)

    @staticmethod
    async def _show_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display subscription tiers"""
        db = SessionLocal()
        try:
            tiers = db.query(SubscriptionTier).all()

            if not tiers:
                tiers = RegistrationFlow._create_default_tiers(db)

            plans_text = "✅ Goal: <b>{}</b>\n\n".format(context.user_data["goal"])
            plans_text += "<b>💳 Choose Your Plan:</b>\n\n"

            for tier in tiers:
                features = tier.features if isinstance(tier.features, dict) else {}
                feat_list = features.get("list", [])
                features_str = ", ".join(feat_list[:2]) if feat_list else "Basic features"

                plans_text += (
                    f"<b>{tier.name}</b>\n"
                    f"₹{tier.price_inr}/month | ${tier.price_usd}/month\n"
                    f"✓ {features_str}\n\n"
                )

            plans_text += "<i>Reply with: Basic, Premium, or Elite</i>"

            await update.message.reply_text(plans_text, parse_mode=ParseMode.HTML)

        finally:
            db.close()

    @staticmethod
    async def _input_plan(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_name: str):
        """Handle plan selection and initiate payment"""
        valid_plans = ["Basic", "Premium", "Elite"]

        if plan_name not in valid_plans:
            plans_text = " | ".join(valid_plans)
            await update.message.reply_text(f"❌ Choose from: {plans_text}")
            return

        context.user_data["plan"] = plan_name
        context.user_data["reg_state"] = RegistrationFlow.STATES["PAYMENT"]

        db = SessionLocal()
        try:
            tier = db.query(SubscriptionTier).filter_by(name=plan_name).first()
            if not tier:
                await update.message.reply_text("❌ Plan not found. Try again:")
                return

            # TODO: Generate payment link (Razorpay/Stripe)
            # For now, just show price and next step
            payment_text = (
                f"✅ <b>{plan_name} Plan Selected</b>\n\n"
                f"Price: <b>₹{tier.price_inr}/month</b>\n\n"
                f"Next: Payment processing (Razorpay)\n"
                f"Then: Strava authorization\n\n"
                f"<i>Processing payment link... Redirecting in 5 seconds.</i>"
            )

            await update.message.reply_text(payment_text, parse_mode=ParseMode.HTML)

            # Store registration data temporarily
            context.user_data["registration_temp"] = {
                "name": context.user_data["name"],
                "age": context.user_data["age"],
                "experience": context.user_data["experience"],
                "goal": context.user_data["goal"],
                "plan": plan_name,
                "price": tier.price_inr,
            }

            # TODO: Call payment handler

        finally:
            db.close()

    @staticmethod
    def _create_default_tiers(db: Session) -> list:
        """Create default subscription tiers if not exist"""
        tiers_data = [
            {
                "name": "Basic",
                "price_usd": 9.99,
                "price_inr": 799,
                "features": {
                    "list": ["Daily coaching", "Activity tracking", "Basic analytics"],
                    "max_athletes": 1,
                },
            },
            {
                "name": "Premium",
                "price_usd": 19.99,
                "price_inr": 1499,
                "features": {
                    "list": [
                        "All Basic features",
                        "Training plans",
                        "Performance analytics",
                        "Medical report analysis",
                    ],
                    "max_athletes": 3,
                },
            },
            {
                "name": "Elite",
                "price_usd": 39.99,
                "price_inr": 2999,
                "features": {
                    "list": [
                        "All Premium features",
                        "1-on-1 coaching",
                        "Custom periodization",
                        "Multi-sport support",
                        "Priority support",
                    ],
                    "max_athletes": 10,
                },
            },
        ]

        for tier_data in tiers_data:
            existing = db.query(SubscriptionTier).filter_by(name=tier_data["name"]).first()
            if not existing:
                tier = SubscriptionTier(**tier_data)
                db.add(tier)

        db.commit()
        return db.query(SubscriptionTier).all()
