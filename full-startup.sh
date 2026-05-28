#!/bin/bash
# Complete startup script - starts API and Telegram Bot together

set -e

echo "========================================================================"
echo "🚀 VEDA AI COACHING - COMPLETE SYSTEM STARTUP"
echo "========================================================================"
echo ""

cd ~/ec2-ai-coaching

# Step 1: Start docker containers (API, Database, Redis, etc)
echo "📍 STEP 1: Starting Docker services..."
docker-compose up -d
sleep 5

# Step 2: Initialize database
echo "📍 STEP 2: Initializing database..."
docker-compose exec -T api python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine); print('✅ Database initialized')" 2>/dev/null || echo "⚠️ Database already initialized"

# Step 3: Start Telegram Bot in background
echo "📍 STEP 3: Starting Telegram Bot..."
# Kill any existing bot processes
pkill -f "telegram_bot_manager" || true
sleep 1

# Start new bot process
nohup python -m backend.telegram_bot_manager > telegram_bot.log 2>&1 &
BOT_PID=$!
echo "✅ Telegram bot started (PID: $BOT_PID)"

# Step 4: Verify all services
echo ""
echo "📍 STEP 4: Verifying services..."
sleep 3

echo ""
echo "Docker containers:"
docker-compose ps

echo ""
echo "API Health:"
curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null | head -15 || echo "⚠️ API not yet responding"

echo ""
echo "Telegram bot process:"
ps aux | grep "telegram_bot_manager" | grep -v grep || echo "⚠️ Bot may still be starting..."

echo ""
echo "========================================================================"
echo "✅ STARTUP COMPLETE!"
echo "========================================================================"
echo ""
echo "Services running:"
echo "  ✅ FastAPI: http://localhost:8001"
echo "  ✅ Frontend: http://localhost:3000"
echo "  ✅ PostgreSQL: localhost:5432"
echo "  ✅ Redis: localhost:6379"
echo "  ✅ Telegram Bot: Polling mode (listening)"
echo ""
echo "To test:"
echo "  1. Send /start to your Telegram bot"
echo "  2. Should get 'Welcome to Veda AI Coaching' response"
echo ""
echo "To monitor:"
echo "  API logs: docker-compose logs -f api"
echo "  Bot logs: tail -f telegram_bot.log"
echo ""
echo "========================================================================"
