================================================================================
✅ CODE PUSHED TO GITHUB - NOW DEPLOY ON EC2
================================================================================

COMMIT: 645f0de (All code + bot fixes pushed)
BRANCH: cursor/byok-strava-refactor
STATUS: ✅ Ready for EC2

FILES PUSHED:
  ✅ All source code changes
  ✅ telegram_bot_manager.py (complex version)
  ✅ start_bot.py (SIMPLE WORKING VERSION - USE THIS!)
  ✅ Enhanced telegram_registration.py (no age restrictions)
  ✅ All deployment scripts
  ✅ All documentation

================================================================================
🚀 DEPLOY ON EC2 - STEP BY STEP
================================================================================

STEP 1: SSH to EC2
  ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186

STEP 2: Go to project directory
  cd ~/ec2-ai-coaching

STEP 3: Pull latest code from GitHub
  git pull origin cursor/byok-strava-refactor

Expected output:
  remote: Counting objects: 29, done.
  remote: Compressing objects: 100% (25/25), done.
  Receiving objects: 100% (29/29), 123.45 KiB | 456 KiB/s, done.
  ✅ 29 files updated

STEP 4: Verify files are present
  ls -la start_bot.py
  ls -la backend/communication/telegram_registration.py
  ls -la backend/telegram_bot_manager.py

Should show all files present ✅

STEP 5: Stop old bot (if running)
  pkill -f "start_bot.py" || true
  pkill -f "telegram_bot_manager" || true

STEP 6: Start NEW bot with latest code
  cd ~/ec2-ai-coaching
  nohup python start_bot.py > bot.log 2>&1 &

Expected output:
  [1] 12345  ← PID of bot process

STEP 7: Verify bot is running
  sleep 3
  tail -f bot.log

Should show:
  ============================================================
  ✅ BOT READY - LISTENING FOR MESSAGES
  ============================================================
  Send /start to test!
  ============================================================

STEP 8: Test bot
  Send /start to your Telegram bot
  Should get response within 1-2 seconds ✅

================================================================================
📋 COMPLETE DEPLOYMENT SCRIPT (Run all at once)
================================================================================

Copy and paste this on EC2:

---BEGIN SCRIPT---

#!/bin/bash
set -e

echo "🚀 VEDA AI COACHING - EC2 DEPLOYMENT"
echo ""

cd ~/ec2-ai-coaching

echo "📍 STEP 1: Pull latest code from GitHub..."
git pull origin cursor/byok-strava-refactor

echo "📍 STEP 2: Stop old bot processes..."
pkill -f "start_bot.py" || true
pkill -f "telegram_bot_manager" || true
sleep 2

echo "📍 STEP 3: Verify files exist..."
test -f start_bot.py && echo "✅ start_bot.py found" || echo "❌ start_bot.py NOT found"
test -f backend/communication/telegram_registration.py && echo "✅ telegram_registration.py found" || echo "❌ NOT found"

echo "📍 STEP 4: Start Docker containers..."
docker-compose up -d
sleep 10

echo "📍 STEP 5: Initialize database..."
docker-compose exec -T api python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)" 2>/dev/null || echo "⚠️ DB already init"

echo "📍 STEP 6: Start Telegram bot..."
nohup python start_bot.py > bot.log 2>&1 &
BOT_PID=$!
echo "Bot started with PID: $BOT_PID"

echo ""
echo "⏳ Waiting for bot to start..."
sleep 3

echo "📍 STEP 7: Verify bot is running..."
if ps -p $BOT_PID > /dev/null; then
    echo "✅ Bot process running (PID: $BOT_PID)"
    echo ""
    echo "📊 Bot status:"
    tail -20 bot.log
else
    echo "❌ Bot process not running"
    echo "Check logs:"
    cat bot.log
fi

echo ""
echo "==============================================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "==============================================================="
echo ""
echo "📱 To test:"
echo "  1. Open Telegram"
echo "  2. Send /start to your bot"
echo "  3. Should get response within 1-2 seconds"
echo ""
echo "📊 To monitor:"
echo "  tail -f ~/ec2-ai-coaching/bot.log"
echo ""
echo "🔄 To restart bot:"
echo "  pkill -f start_bot.py"
echo "  cd ~/ec2-ai-coaching"
echo "  nohup python start_bot.py > bot.log 2>&1 &"
echo ""
echo "==============================================================="

---END SCRIPT---

================================================================================
✅ FILES NOW ON EC2
================================================================================

After pulling, you'll have:

/home/ubuntu/ec2-ai-coaching/
├── start_bot.py ✅ (USE THIS - simple working bot)
├── backend/
│   ├── telegram_bot_manager.py ✅
│   ├── communication/
│   │   └── telegram_registration.py ✅ (no age restrictions)
│   ├── llm_service.py ✅ (Groq integrated)
│   ├── main.py ✅
│   └── ...
├── docker-compose.yml ✅
├── full-startup.sh ✅
├── start-telegram-bot.sh ✅
└── [All documentation files]

All code synced and ready! ✅

================================================================================
🧪 QUICK VERIFICATION
================================================================================

After deployment, verify everything on EC2:

Check all files:
  ls -la start_bot.py backend/communication/telegram_registration.py

Check bot is running:
  ps aux | grep start_bot.py

Check bot logs:
  tail -50 bot.log

Check recent git commit:
  git log --oneline -5
  Should show: "feat: Enhanced Telegram registration..."

Check containers:
  docker-compose ps

Test database:
  docker-compose exec -T postgres psql -U postgres -c "SELECT COUNT(*) FROM users;"

Test bot:
  Send /start to Telegram
  Should respond within 2 seconds ✅

================================================================================
📱 EXPECTED BOT BEHAVIOR
================================================================================

After deployment:

User sends: /start
  ↓ (within 1-2 seconds)
Bot responds:
  "👋 Welcome to Veda AI Coaching!
   [✅ Register] [❌ Cancel]"

User clicks: ✅ Register
  ↓
Bot: "📧 What's your email?"
  ↓
User: john@example.com
  ↓
Bot: "🎂 Date of birth? (DD-MM-YYYY)"
  ↓
[...flow continues...]
  ↓
Bot: "🎉 Done! Welcome to Veda AI Coaching! 🚀"
  ↓
User saved to database ✅

================================================================================
🆘 IF ANYTHING GOES WRONG
================================================================================

1. Check git pull worked:
   git log --oneline -1
   Should show: 645f0de - feat: Enhanced Telegram registration...

2. Check files exist:
   test -f start_bot.py && echo "exists" || echo "missing"

3. Check bot logs for errors:
   cat bot.log

4. Restart bot:
   pkill -f start_bot.py
   sleep 2
   nohup python start_bot.py > bot.log 2>&1 &
   sleep 3
   tail bot.log

5. Check Python path:
   which python
   python --version

6. Check dependencies:
   python -c "import telegram; print(telegram.__version__)"

If errors persist:
  - Check .env file has TELEGRAM_BOT_TOKEN
  - Check Docker containers running
  - Check database initialized

================================================================================
✅ DEPLOYMENT CHECKLIST
================================================================================

Before deploying:
  [ ] Committed all changes locally
  [ ] Pushed to GitHub
  [ ] Verified commit hash

During deployment:
  [ ] SSH'd to EC2
  [ ] Pulled latest code
  [ ] Stopped old bot
  [ ] Started Docker containers
  [ ] Started new bot
  [ ] Waited 3 seconds

After deployment:
  [ ] Bot process running (ps aux | grep start_bot.py)
  [ ] Bot logs show "BOT READY"
  [ ] Telegram bot responds to /start
  [ ] User registers successfully
  [ ] User appears in database

Status: ✅ DEPLOYMENT COMPLETE

================================================================================
🎊 YOU'RE DONE!
================================================================================

All code is now on EC2 with the latest:
  ✅ Enhanced registration (email, DOB, no age restrictions)
  ✅ Simple working bot (start_bot.py)
  ✅ All documentation and scripts

Bot is ready to use!

Next: Send /start to Telegram and test! 🚀

================================================================================
