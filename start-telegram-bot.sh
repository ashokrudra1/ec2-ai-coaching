#!/bin/bash
# Telegram Bot Startup Script - Run this on EC2 to start the bot

set -e

echo "========================================================================"
echo "🤖 VEDA AI COACHING - TELEGRAM BOT STARTUP"
echo "========================================================================"
echo ""

cd ~/ec2-ai-coaching

echo "📍 Starting Telegram Bot in background mode..."
echo ""

# Start telegram bot in polling mode in a detached screen session
# This allows the bot to run independently while the FastAPI server also runs

# Install python-telegram-bot if needed
pip install python-telegram-bot --quiet 2>/dev/null || echo "python-telegram-bot already installed"

# Run telegram bot in background
echo "Starting bot with polling..."
nohup python -m backend.telegram_bot_manager > telegram_bot.log 2>&1 &

echo "✅ Telegram bot started!"
echo ""
echo "Bot is now running in polling mode"
echo "Check logs: tail -f telegram_bot.log"
echo ""
echo "Test: Send /start to your Telegram bot"
echo ""
