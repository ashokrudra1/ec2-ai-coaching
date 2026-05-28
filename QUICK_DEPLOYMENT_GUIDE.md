================================================================================
⚡ QUICK START GUIDE - ENHANCED REGISTRATION DEPLOYMENT
================================================================================

🎯 WHAT YOU'RE DEPLOYING:

New Features:
  ✅ Email collection during registration
  ✅ Date of birth collection (validation included)
  ✅ Experience level selection (3 options)
  ✅ Personal Strava token support
  ✅ LIVE sync updates shown in Telegram

Registration Flow Time: ~5 minutes per user

================================================================================
🚀 DEPLOYMENT - ONE COMMAND
================================================================================

SSH to EC2:
  ssh -i "coaching.pem" ubuntu@13.233.127.186
  cd ec2-ai-coaching

Deploy:
  bash deploy-enhanced.sh

Wait: 2-3 minutes for build & start

Verify:
  curl http://localhost:8001/health

================================================================================
🧪 TEST THE NEW REGISTRATION
================================================================================

1. Open Telegram
2. Search for your bot
3. Send: /start
4. Follow registration:
   - Email: john@example.com
   - DOB: 15-03-1990
   - Experience: Advanced
   - Strava: Connect (see live updates!)
5. Complete registration
6. Chat with coach!

================================================================================
💾 VERIFY IN DATABASE
================================================================================

Check users:
  docker-compose exec -T postgres psql -U postgres -c "SELECT id, name, email, dob, experience_level FROM users;"

Check specific user:
  docker-compose exec -T postgres psql -U postgres -c "SELECT * FROM users WHERE id = 1;"

Delete test users:
  docker-compose exec -T postgres psql -U postgres -c "DELETE FROM users WHERE telegram_chat_id = '123456';"

================================================================================
📊 WHAT'S STORED IN DATABASE
================================================================================

For each user:
  - Name ✅
  - Email ✅ (NEW)
  - DOB ✅ (NEW)
  - Experience Level ✅ (NEW)
  - Telegram ID ✅
  - Strava Athlete ID ✅
  - Activities ✅ (synced every 5 min)
  - Coaching Memory ✅
  - Performance Metrics ✅

Sample user after registration:
  id: 1
  name: John Smith
  email: john@example.com
  dob: 1990-03-15
  experience_level: advanced
  telegram_chat_id: 987654321
  is_active: true
  created_at: 2026-05-28 12:30:00

================================================================================
🔍 MONITORING
================================================================================

Watch logs:
  docker-compose logs -f api

Filter for registration:
  docker-compose logs -f api | grep -i "registration\|strava\|sync"

Check health:
  curl http://localhost:8001/health | python3 -m json.tool

List containers:
  docker-compose ps

================================================================================
⚠️ TROUBLESHOOTING
================================================================================

If registration fails:
  1. Check logs: docker-compose logs api
  2. Verify Groq API key: cat .env | grep OPENAI
  3. Check database: docker-compose exec -T postgres psql -U postgres -c "SELECT COUNT(*) FROM users;"

If Strava sync doesn't show:
  1. User needs to provide Personal Access Token from Strava
  2. Token format: Long alphanumeric string (50+ characters)
  3. Get from: strava.com → Settings → API

If email validation fails:
  1. Must contain @ symbol
  2. Must contain . (dot)
  3. Example: john@example.com ✅

If DOB validation fails:
  1. Format must be: DD-MM-YYYY
  2. Age must be 18-100
  3. Examples:
     - 15-03-1990 ✅ (age 35)
     - 01-01-2008 ✅ (age 18)
     - 15-03-2010 ❌ (age 16, too young)
     - 1990-03-15 ❌ (wrong format)

================================================================================
📱 USER FLOW SUMMARY
================================================================================

/start
   ↓
Register? → No: Exit | Yes: Continue
   ↓
📧 Email? → Validate → Store
   ↓
🎂 DOB? (DD-MM-YYYY) → Validate → Store
   ↓
🏃 Experience? → Select → Store
   ↓
🔗 Strava? → Connect: OAuth flow | Skip: Continue
   ↓
📋 Review all data
   ↓
✅ Complete registration
   ↓
🎉 Account created!
   ↓
Ready for coaching 🚀

================================================================================
✨ KEY COMMANDS
================================================================================

Deployment:
  bash deploy-enhanced.sh

Logs:
  docker-compose logs -f api

Health check:
  curl http://localhost:8001/health

Database check:
  docker-compose exec -T postgres psql -U postgres -c "SELECT * FROM users LIMIT 5;"

Database reset:
  docker-compose exec -T postgres psql -U postgres -c "DELETE FROM users;"

Restart services:
  docker-compose restart

Stop all:
  docker-compose down

Start all:
  docker-compose up -d

================================================================================
🎯 NEXT STEPS
================================================================================

1. Deploy:
   bash deploy-enhanced.sh

2. Wait 2-3 minutes

3. Test registration:
   Send /start on Telegram

4. Complete entire flow:
   Email → DOB → Experience → Strava → Confirm

5. Verify in database:
   docker-compose exec -T postgres psql -U postgres -c "SELECT * FROM users;"

6. Check coaching:
   Send message to bot → Get Groq response

7. Monitor:
   docker-compose logs -f api

8. Repeat step 3-7 with fresh users for testing

DONE! 🎉

================================================================================
💬 NEW USER EXPERIENCE
================================================================================

User perspective:

1. Clicks bot link in Telegram
2. Sends /start
3. Sees: "Welcome to Veda AI Coaching!"
4. Enters email: john@example.com
5. Enters DOB: 15-03-1990
6. Selects experience: Advanced
7. Connects Strava (sees live updates):
   ✅ Profile loaded
   ✅ 15 activities found
   ✅ Processing...
   ✅ Done!
8. Reviews profile
9. Clicks "Complete Registration"
10. Gets welcome message
11. Ready to chat with coach!

Total time: ~5 minutes

User feels: Professional, transparent, welcomed ✨

================================================================================
📞 SUPPORT
================================================================================

Issue: User can't register
Fix: Check logs, verify email/DOB format

Issue: Strava won't connect
Fix: User needs Personal Access Token from Strava

Issue: No coaching response
Fix: Verify Groq API key in .env

Issue: Database empty
Fix: User registration completed but not in DB? Check logs for errors

For urgent help:
  docker-compose logs api | tail -50

================================================================================
✅ READY TO DEPLOY!
================================================================================

All features tested and ready.
Database schema compatible.
Code committed.
Deployment script automated.

Run: bash deploy-enhanced.sh

Then test with: /start on Telegram

That's it! 🚀

================================================================================
