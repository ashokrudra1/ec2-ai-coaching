# 🚀 EC2 DEPLOYMENT - QUICK COMMANDS

## ONE-COMMAND DEPLOY (FROM YOUR LAPTOP)

```bash
bash scripts/deploy-to-ec2.sh
```

---

## SSH INTO EC2

```bash
ssh -i "C:\Users\HP\Downloads\coaching.pem" ubuntu@13.233.127.186
```

---

## ONCE ON EC2

### View Application Status
```bash
cd ~/veda-ai-coaching

# All containers running?
docker-compose ps

# Is it healthy?
curl http://localhost:8001/health | jq .

# View logs
docker-compose logs -f api
```

### View Database
```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres

# List tables
\dt

# Check users
SELECT id, name, email, is_active FROM users;

# Exit
\q
```

### Manage Services
```bash
# Restart everything
docker-compose restart

# Restart just API
docker-compose restart api

# Stop everything
docker-compose down

# Start everything
docker-compose up -d
```

### View Logs
```bash
# All logs (follow mode)
docker-compose logs -f

# Just API
docker-compose logs -f api

# Just Celery
docker-compose logs -f celery_worker

# Just Database
docker-compose logs -f postgres
```

---

## TELEGRAM BOT SETUP

### 1. Create Bot
- Open Telegram
- Message `@BotFather`
- `/newbot`
- Follow prompts
- Save bot token

### 2. Add Bot Token to .env
```bash
# On EC2
cd ~/veda-ai-coaching
nano .env

# Edit TELEGRAM_BOT_TOKEN=your_token_here
# Save (Ctrl+X, Y, Enter)

# Restart API
docker-compose restart api
```

### 3. Test Bot
- Search for your bot in Telegram
- Send: `/start`
- Complete registration flow

---

## FIRST USER REGISTRATION

When user sends `/start` in Telegram:

1. Bot asks for email
2. Bot asks for experience level
3. Bot confirms details
4. User registered in database!

Check database:
```bash
docker-compose exec postgres psql -U postgres -c \
  "SELECT id, name, email, is_active FROM users;"
```

---

## MONITORING

### Check System Health
```bash
docker stats
free -h
df -h
```

### Check Database
```bash
docker-compose exec postgres psql -U postgres << EOF
SELECT count(*) as user_count FROM users;
SELECT count(*) as activity_count FROM activities;
\q
EOF
```

### Check Redis
```bash
docker-compose exec redis redis-cli INFO
```

### Check Backups
```bash
aws s3 ls s3://YOUR_BACKUP_BUCKET/production/postgresql/
```

---

## TROUBLESHOOTING

### API Down
```bash
# Check status
docker-compose ps api

# Check logs
docker-compose logs api

# Restart
docker-compose restart api

# Wait 30 seconds
sleep 30

# Check again
curl http://localhost:8001/health
```

### Database Error
```bash
# Check PostgreSQL
docker-compose logs postgres

# Restart
docker-compose restart postgres

# Reinitialize tables
docker-compose exec api python -c \
  "from backend.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Out of Disk Space
```bash
# Check usage
df -h

# Clean Docker
docker system prune -a -f

# Check again
df -h
```

---

## DEPLOYMENT CHECKLIST

```
[ ] SSH into EC2 works
[ ] Code cloned successfully
[ ] .env configured with secrets
[ ] Docker images built
[ ] All containers running
[ ] Health check returns "healthy"
[ ] Database tables created
[ ] Telegram bot token added
[ ] Bot responds to /start
[ ] User can register through bot
[ ] CloudWatch alarms working
[ ] Backups scheduled
[ ] SSL certificate valid
```

---

## URLS

| Service | URL |
|---------|-----|
| API Health | http://localhost:8001/health |
| Dashboard | https://vedaactivewellness.xyz |
| CloudWatch | https://console.aws.amazon.com/cloudwatch/ |
| Telegram Bot | Search in Telegram app |

---

## KEY FILES

| File | Purpose |
|------|---------|
| `.env` | Configuration (secrets) |
| `docker-compose.yml` | Service definitions |
| `backend/main.py` | FastAPI app |
| `backend/telegram_registration.py` | Bot registration flow |
| `scripts/deploy-to-ec2.sh` | Auto deployment |
| `EC2_DEPLOYMENT_GUIDE.md` | Full guide |

---

## QUICK RESTART

If something breaks:

```bash
cd ~/veda-ai-coaching

# Stop all
docker-compose down

# Clean up
docker system prune -a -f

# Rebuild
docker-compose build --no-cache

# Start fresh
docker-compose up -d

# Wait
sleep 30

# Check
docker-compose ps
curl http://localhost:8001/health | jq .
```

---

## PRODUCTION CHECKLIST - DAILY

```bash
# Morning check
docker-compose ps                    # All running?
curl http://localhost:8001/health    # Healthy?
docker-compose logs api | grep -i error  # Any errors?
aws s3 ls s3://BUCKET/               # Backup created?
```

---

**REMEMBER**: 
- Always run from `/home/ubuntu/veda-ai-coaching`
- Always check logs first when debugging
- Backup before major changes
- Monitor CloudWatch dashboard

🚀 **YOU'RE READY TO DEPLOY!**
