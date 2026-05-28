#!/bin/bash
# EC2 FINAL SETUP - Run these commands on your EC2 instance

cd ~/ec2-ai-coaching

# ============================================================================
# STEP 1: CREATE .env FILE
# ============================================================================
echo "Creating .env file..."
cp .env.example .env

# ============================================================================
# STEP 2: INITIALIZE DATABASE (CREATE TABLES)
# ============================================================================
echo "Initializing database..."
docker-compose exec -T api python -c \
  "from backend.database import Base, engine; Base.metadata.create_all(bind=engine); print('✅ Database tables created')"

# ============================================================================
# STEP 3: VERIFY ALL SERVICES
# ============================================================================
echo ""
echo "Checking all services..."
docker-compose ps

echo ""
echo "Checking health endpoint..."
curl -s http://localhost:8001/health | python3 -m json.tool

# ============================================================================
# STEP 4: VERIFY DATABASE TABLES
# ============================================================================
echo ""
echo "Verifying database tables..."
docker-compose exec -T postgres psql -U postgres -c "
SELECT COUNT(*) as table_count FROM information_schema.tables 
WHERE table_schema = 'public';
"

# ============================================================================
# STEP 5: DISPLAY NEXT STEPS
# ============================================================================
echo ""
echo "======================================================================="
echo "✅ EC2 DEPLOYMENT COMPLETE!"
echo "======================================================================="
echo ""
echo "🔐 NEXT: Configure Telegram Bot"
echo ""
echo "1. Create bot with @BotFather (if not done)"
echo "2. Get bot token"
echo "3. Edit .env file:"
echo "   nano .env"
echo "   Find: TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here"
echo "   Replace with your actual token"
echo "   Save: Ctrl+X, then Y, then Enter"
echo ""
echo "4. Restart API to load new token:"
echo "   docker-compose restart api"
echo ""
echo "5. Wait 10 seconds:"
echo "   sleep 10"
echo ""
echo "6. Test bot in Telegram:"
echo "   - Search for your bot"
echo "   - Send: /start"
echo "   - Complete registration"
echo ""
echo "======================================================================="
echo ""
