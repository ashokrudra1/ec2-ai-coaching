# 🚀 EC2 DEPLOYMENT - COMPLETE GUIDE

## ONE-COMMAND DEPLOYMENT

Run this from your local machine to deploy everything to EC2:

```bash
# From project root directory
bash scripts/deploy-to-ec2.sh
```

This will:
1. ✅ Push all code to EC2
2. ✅ Apply security hardening
3. ✅ Build Docker images
4. ✅ Start all services
5. ✅ Initialize database
6. ✅ Configure CloudWatch monitoring
7. ✅ Schedule daily backups

**Deployment Time: ~20 minutes**

---

## MANUAL DEPLOYMENT (If Script Fails)

### Step 1: SSH into EC2

```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186
```

### Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/YOUR_REPO/ec2-ai-coaching.git
cd ec2-ai-coaching
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your secrets
nano .env

# IMPORTANT: Fill in these values:
DATABASE_PASSWORD=<strong_password>
POSTGRES_PASSWORD=<strong_password>
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=<your_bot_token>
STRAVA_CLIENT_SECRET=<strava_secret>
ADMIN_API_KEY=<strong_random_key>
AWS_REGION=ap-south-1
S3_BACKUP_BUCKET=<your_backup_bucket>
DOMAIN=vedaactivewellness.xyz
```

### Step 4: Apply Security Hardening

```bash
chmod +x scripts/*.sh
bash scripts/ec2-security-hardening.sh
```

### Step 5: Start Services

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Wait for initialization
sleep 30

# Check status
docker-compose ps
```

### Step 6: Initialize Database

```bash
# Create all tables
docker-compose exec api python -c \
  "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Verify
docker-compose exec postgres psql -U postgres -c "\dt"
```

### Step 7: Verify Deployment

```bash
# Check health
curl http://localhost:8001/health | jq .

# Expected output:
# "status": "healthy"

# Check logs
docker-compose logs api | tail -20
```

---

## 🤖 TELEGRAM BOT SETUP

### 1. Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Follow prompts to create bot
4. Save the **bot token** (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. Configure Bot Token in .env

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

### 3. Setup Webhook

```bash
# Set webhook endpoint
curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook \
  -d "url=https://vedaactivewellness.xyz/webhook/telegram" \
  -d "secret_token=$TELEGRAM_SECRET_TOKEN"

# Verify webhook
curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo | jq .
```

### 4. Test Bot

1. Find your bot in Telegram (search for bot name)
2. Send: `/start`
3. Bot will guide through registration

---

## 📋 FIRST USER REGISTRATION FLOW

### Via Telegram Bot

```
User: /start
Bot: "Welcome to Veda AI Coaching..."
     [✅ Register] [❌ Cancel]

User: Clicks "Register"
Bot: "What's your email?"

User: user@example.com
Bot: "What's your experience level?"
     [🟢 Beginner] [🟡 Intermediate] [🔴 Advanced]

User: Clicks "Intermediate"
Bot: "Registration Summary
      Name: John
      Email: john@example.com
      Experience: Intermediate
      
      Is everything correct?"
     [✅ Complete] [✏️ Edit]

User: Clicks "Complete"
Bot: "🎉 Registration Complete!
      Your account is ready.
      Connect Strava to start coaching."
     [📊 Connect Strava] [📝 View Profile] [❓ Help]
```

---

## ✅ VERIFICATION CHECKLIST

After deployment, verify everything works:

```bash
# 1. Check all containers running
docker-compose ps
# All should show "Up" status

# 2. Check health endpoint
curl https://vedaactivewellness.xyz/health | jq .
# Should return: "status": "healthy"

# 3. Check API responds
curl https://vedaactivewellness.xyz/api/stats | jq .

# 4. Check SSL certificate
curl -I https://vedaactivewellness.xyz | grep "HTTP"
# Should return: HTTP/2 200

# 5. Check database has tables
docker-compose exec postgres psql -U postgres -c "\dt" | wc -l
# Should show > 10 tables

# 6. Check CloudWatch alarms
aws cloudwatch describe-alarms --region ap-south-1 | jq '.MetricAlarms | length'
# Should show: 6

# 7. Test backup script
bash scripts/backup-to-s3.sh
aws s3 ls s3://YOUR_BUCKET/production/postgresql/
# Should show backup file
```

---

## 🔒 SECURITY CHECKLIST

- [ ] SSH key-based authentication only (no passwords)
- [ ] UFW firewall enabled (ports 22, 80, 443)
- [ ] fail2ban configured
- [ ] .env file not in git
- [ ] Automatic security updates enabled
- [ ] SSL/TLS certificate auto-renewed
- [ ] CloudWatch monitoring active
- [ ] Daily backups to S3
- [ ] Sentry error tracking configured
- [ ] Rate limiting enabled (100/min per IP)

---

## 📊 MONITORING DASHBOARD

Monitor your deployment:

```bash
# View all logs (follow mode)
docker-compose logs -f

# View specific service
docker-compose logs -f api
docker-compose logs -f celery_worker
docker-compose logs -f postgres

# Check container stats
docker stats

# Monitor health
watch -n 10 'curl -s http://localhost:8001/health | jq ".components"'
```

---

## 🔄 USEFUL COMMANDS

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart api

# Stop all services
docker-compose down

# View database
docker-compose exec postgres psql -U postgres -c "SELECT * FROM users LIMIT 5;"

# Check Redis
docker-compose exec redis redis-cli INFO

# View Celery workers
docker exec celery_worker celery -A backend.celery_app inspect active

# Manually trigger backup
bash scripts/backup-to-s3.sh

# View backup logs
tail -f /var/log/backup.log

# Check disk usage
df -h
du -sh /var/lib/docker/*
```

---

## 🆘 TROUBLESHOOTING

### API not responding

```bash
# Check if running
docker-compose ps api

# View logs
docker-compose logs api | tail -50

# Restart
docker-compose restart api
```

### Database tables missing

```bash
# Create tables
docker-compose exec api python -c \
  "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Verify
docker-compose exec postgres psql -U postgres -c "\dt"
```

### Health check failing

```bash
# Check each component
curl http://localhost:8001/health | jq '.components'

# If PostgreSQL failing
docker-compose restart postgres

# If Redis failing
docker-compose restart redis
```

### Disk space low

```bash
# Check usage
df -h

# Clean Docker
docker system prune -a -f

# Clean logs
docker-compose exec postgres vacuumdb -U postgres
```

### SSL certificate issue

```bash
# Check certificate
echo | openssl s_client -servername vedaactivewellness.xyz -connect vedaactivewellness.xyz:443 | openssl x509 -noout -dates

# Restart Caddy (Caddy auto-renews)
docker-compose restart caddy
```

---

## 📞 SUPPORT

**SSH to EC2**:
```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186
```

**View logs**:
```bash
docker-compose logs -f
```

**Check status**:
```bash
docker-compose ps
curl https://vedaactivewellness.xyz/health | jq .
```

**CloudWatch Dashboard**:
https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1

---

## ✨ DEPLOYMENT COMPLETE!

Your Veda AI Coaching system is now **LIVE** on EC2!

**Next Steps**:
1. ✅ Create Telegram bot with @BotFather
2. ✅ Add users through `/start` command
3. ✅ Monitor CloudWatch dashboard
4. ✅ Review logs regularly
5. ✅ Test backup/restore weekly

**Status**: 🟢 LIVE AND RUNNING

**Last Updated**: December 2024  
**Version**: 4.2.0  
**Environment**: Production (EC2)
