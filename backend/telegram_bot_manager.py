"""
Telegram Bot Initialization & Management - FIXED VERSION
Starts the Telegram bot with registration and coaching handlers
Handles polling and webhook modes
"""
import os
import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

# Import handlers
from backend.communication.telegram_registration import TelegramUserRegistration, setup_telegram_registration
from backend.communication.telegram_coaching_handler import (
    CoachingMessageHandler,
    setup_coaching_handlers
)


class TelegramBotManager:
    """
    Manages Telegram bot lifecycle, registration, and coaching.
    Handles polling and webhook modes.
    """
    
    def __init__(self):
        self.app = None
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not self.bot_token:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
            raise ValueError("TELEGRAM_BOT_TOKEN is required to start the bot")
        
        logger.info(f"✅ Bot token loaded: {self.bot_token[:20]}...")
    
    async def initialize(self):
        """Initialize the Telegram bot application"""
        logger.info("🤖 Initializing Telegram Bot Manager")
        
        # Create application
        self.app = Application.builder().token(self.bot_token).build()
        
        logger.info("📍 Setting up registration handlers...")
        await setup_telegram_registration(self.app)
        
        logger.info("📍 Setting up coaching handlers...")
        await setup_coaching_handlers(self.app)
        
        logger.info("✅ Telegram bot initialized successfully")
        logger.info("=" * 80)
        logger.info("🟢 BOT STATUS: READY FOR MESSAGES")
        logger.info("=" * 80)
        
        return self.app
    
    async def start_polling(self):
        """Start bot in polling mode (for development)"""
        if not self.app:
            await self.initialize()
        
        logger.info("🔄 Starting Telegram bot polling...")
        logger.info("⏳ Bot is now listening for messages...")
        logger.info("✅ Bot is LIVE - send /start to test!")
        logger.info("=" * 80)
        
        try:
            await self.app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"❌ Polling error: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop the bot gracefully"""
        if self.app:
            logger.info("🛑 Stopping Telegram bot...")
            await self.app.stop()
            logger.info("✅ Telegram bot stopped")


# ============================================================================
# MAIN ENTRY POINT - Run directly with: python -m backend.telegram_bot_manager
# ============================================================================
async def main():
    """Main entry point - starts the bot"""
    
    logger.info("=" * 80)
    logger.info("🚀 VEDA AI COACHING - TELEGRAM BOT STARTUP")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        manager = TelegramBotManager()
        await manager.start_polling()
    
    except KeyboardInterrupt:
        logger.info("\n👋 Bot stopped by user (Ctrl+C)")
    
    except Exception as e:
        logger.error(f"❌ FATAL ERROR: {e}", exc_info=True)
        logger.error("Check your TELEGRAM_BOT_TOKEN in .env file")
        raise


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    
    # Load .env file
    load_dotenv()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        sys.exit(1)
