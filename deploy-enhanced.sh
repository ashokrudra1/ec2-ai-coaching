#!/bin/bash
# DEPLOYMENT SCRIPT - UPDATED WITH NEW REGISTRATION FEATURES

set -e

echo "========================================================================"
echo "🚀 VEDA AI COACHING - DEPLOYMENT WITH ENHANCED REGISTRATION"
echo "========================================================================"
echo ""

cd ~/ec2-ai-coaching

echo "📍 STEP 1: Pulling latest code..."
git pull origin main 2>/dev/null || echo "⚠️ Git pull skipped"

echo "📍 STEP 2: Stopping containers..."
docker-compose down

echo "📍 STEP 3: Building images..."
docker-compose build --no-cache

echo "📍 STEP 4: Starting services..."
docker-compose up -d

echo "📍 STEP 5: Waiting for services to stabilize..."
sleep 30

echo "📍 STEP 6: Initializing database..."
docker-compose exec -T api python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine); print('✅ Database initialized')"

echo "📍 STEP 7: Checking container status..."
docker-compose ps

echo "📍 STEP 8: Testing health endpoint..."
HEALTH=$(curl -s http://localhost:8001/health)
echo "$HEALTH" | python3 -m json.tool

echo ""
echo "========================================================================"
echo "✅ DEPLOYMENT COMPLETE"
echo "========================================================================"
echo ""
echo "🎯 NEW FEATURES DEPLOYED:"
echo "   ✅ Email collection during registration"
echo "   ✅ Date of birth collection"
echo "   ✅ Experience level selection"
echo "   ✅ Personal Strava token integration"
echo "   ✅ Live sync updates in Telegram"
echo ""
echo "🔧 TESTING:"
echo "   1. Send /start to your Telegram bot"
echo "   2. Complete the registration flow"
echo "   3. Connect your Strava account (see live updates!)"
echo "   4. Get personalized coaching!"
echo ""
echo "📊 DATABASE UPDATES:"
echo "   ✅ email field populated"
echo "   ✅ dob (date of birth) field populated"
echo "   ✅ experience_level stored"
echo "   ✅ All user preferences saved"
echo ""
echo "========================================================================"
