# 🎯 FINAL - DEPLOY TO EC2 AND GO LIVE

## STEP 1: DEPLOY FROM YOUR LAPTOP (5 MINUTES)

Run this command from your project directory:

```bash
bash scripts/deploy-to-ec2.sh
```

**This will:**
✅ Connect to EC2 via SSH  
✅ Push all code to EC2  
✅ Build Docker images  
✅ Start all services  
✅ Initialize database  
✅ Configure monitoring  

**Expected output: ✅ DEPLOYMENT COMPLETE!**

---

## STEP 2: CONFIGURE TELEGRAM BOT (5 MINUTES)

### A. Create Bot in Telegram

1. Open Telegram app
2. Search for `@BotFather`
3. Send: `/newbot`
4. Follow instructions (name, username)
5. **SAVE THE BOT TOKEN** (looks like: `1234567890:ABCDEFghijklmnopqrstuvwxyz`)

### B. Add Token to EC2

```bash
# SSH into EC2
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186

# Navigate to app
cd ~/veda-ai-coaching

# Edit configuration
nano .env

# Find this line and replace:
# OLD: TELEGRAM_BOT_TOKEN=
# NEW: TELEGRAM_BOT_TOKEN=1234567890:ABCDEFghijklmnopqrstuvwxyz

# Save and exit (Ctrl+X, then Y, then Enter)

# Restart API to load new token
docker-compose restart api

# Wait 10 seconds
sleep 10

# Verify
curl http://localhost:8001/health | jq '.status'
```

---

## STEP 3: TEST REGISTRATION (2 MINUTES)

### A. In Telegram App

1. Search for your bot (by username you created)
2. Send: `/start`
3. Bot will respond with welcome message
4. Click: "✅ Register"
5. Enter your email
6. Choose experience level
7. Confirm registration
8. Done! ✅

### B. Verify in Database

```bash
# SSH into EC2
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186

# Connect to database
cd ~/veda-ai-coaching && docker-compose exec postgres psql -U postgres

# List users
SELECT id, name, email, telegram_chat_id, is_active FROM users;

# Exit
\q
```

Expected output:
```
 id |  name  |      email      | telegram_chat_id | is_active 
----+--------+-----------------+------------------+-----------
  1 | YourName | your@email.com |      123456789   | t
```

---

## STEP 4: VERIFY LIVE DEPLOYMENT (2 MINUTES)

```bash
# SSH into EC2
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186

cd ~/veda-ai-coaching

# Test 1: API Health
echo "✓ Testing API health..."
curl -s http://localhost:8001/health | jq '.status'
# Expected: "healthy"

# Test 2: Database Connected
echo "✓ Testing database..."
docker-compose exec postgres psql -U postgres -c "SELECT 1"
# Expected: "1"

# Test 3: Redis Connected
echo "✓ Testing Redis..."
docker-compose exec redis redis-cli ping
# Expected: "PONG"

# Test 4: All Containers Running
echo "✓ Checking containers..."
docker-compose ps
# Expected: All showing "Up"

# Test 5: Frontend Accessible
echo "✓ Testing frontend..."
curl -I http://localhost:3000
# Expected: "200 OK"
```

---

## STEP 5: MONITOR FIRST USERS (ONGOING)

```bash
# SSH into EC2
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186

cd ~/veda-ai-coaching

# Watch for new registrations
watch -n 5 'docker-compose exec -T postgres psql -U postgres -c "SELECT id, name, email, created_at FROM users ORDER BY created_at DESC LIMIT 5;"'

# View real-time logs
docker-compose logs -f api

# Check API usage
curl -s http://localhost:8001/health | jq '.components'
```

---

## 🎯 YOUR DEPLOYMENT COMMAND SUMMARY

**Copy and paste these in order:**

### On Your Laptop:
```bash
cd ~/path/to/veda-ai-coaching
bash scripts/deploy-to-ec2.sh
# Follow the prompts
```

### Then SSH to EC2:
```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186
cd ~/veda-ai-coaching
nano .env
# Edit TELEGRAM_BOT_TOKEN value
# Save (Ctrl+X, Y, Enter)
docker-compose restart api
sleep 10
curl http://localhost:8001/health | jq '.status'
```

### Test in Telegram:
- Search for your bot
- Send `/start`
- Complete registration

---

## 📊 WHAT HAPPENS AFTER DEPLOYMENT

### User Registration Flow (via Telegram):

```
1. User sends /start
   ↓
2. Bot asks for email
   ↓
3. Bot asks for experience level
   ↓
4. Bot shows confirmation
   ↓
5. User clicks "Complete"
   ↓
6. ✅ User created in database
   ↓
7. Bot offers to connect Strava
```

### Behind the Scenes:

- ✅ User data saved to PostgreSQL
- ✅ Telegram ID linked to user account
- ✅ Registration logged in application
- ✅ Ready for Strava integration
- ✅ Celery tasks can start
- ✅ CloudWatch metrics tracked

---

## 🔒 SECURITY NOTES

✅ All secrets in `.env` file (never in code)  
✅ SSH key-only authentication to EC2  
✅ Rate limiting: 100 requests/minute  
✅ Auto-renewal of SSL certificate  
✅ Daily backups to S3  
✅ CloudWatch monitoring 24/7  
✅ Firewall: Only ports 22, 80, 443  
✅ DDoS protection: fail2ban enabled  

---

## 📞 IF SOMETHING GOES WRONG

### Check Logs:
```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186
cd ~/veda-ai-coaching
docker-compose logs api | tail -50
```

### Restart Services:
```bash
docker-compose restart
sleep 30
docker-compose ps
```

### Reinitialize Database:
```bash
docker-compose exec api python -c \
  "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Check Health:
```bash
curl http://localhost:8001/health | jq .
```

---

## 📈 MONITORING DASHBOARD

View production metrics: https://console.aws.amazon.com/cloudwatch/

**Alarms Configured:**
- ✓ High CPU (>80% for 5 min)
- ✓ High Memory (>85%)
- ✓ Low Disk Space (<10%)
- ✓ High API Latency (p99 >1s)
- ✓ Slow Database (queries >5s)
- ✓ Health Check Failed

---

## ✅ COMPLETION CHECKLIST

- [ ] `bash scripts/deploy-to-ec2.sh` completed successfully
- [ ] SSH to EC2 works
- [ ] `.env` file configured with bot token
- [ ] `docker-compose ps` shows all containers "Up"
- [ ] `curl http://localhost:8001/health` returns "healthy"
- [ ] Telegram bot created and token added
- [ ] Bot responds to `/start` command
- [ ] User can complete registration through bot
- [ ] New user appears in database
- [ ] CloudWatch dashboard accessible
- [ ] Backups running to S3

---

## 🚀 YOU'RE LIVE!

**Status**: ✅ PRODUCTION DEPLOYMENT COMPLETE

Your Veda AI Coaching system is now:
- ✅ Running on EC2
- ✅ Accessible via domain
- ✅ Accepting user registrations via Telegram
- ✅ Backed up daily to S3
- ✅ Monitored 24/7 with CloudWatch
- ✅ Secured with SSL/TLS
- ✅ Protected with rate limiting and firewall

**Next Steps**:
1. Share Telegram bot link with users
2. Monitor registrations
3. Help users connect Strava
4. Start coaching!

---

**Version**: 4.2.0 PRODUCTION  
**Deployed**: [Date]  
**Status**: 🟢 LIVE  
**Users**: Ready to onboard  

🎉 **CONGRATULATIONS! YOU'RE DEPLOYED AND LIVE!**
