================================================================================
GROQ PRODUCTION DEPLOYMENT - QUICK COMMAND REFERENCE
================================================================================

🚀 QUICK DEPLOY (All-in-one):
================================================================================

cd ~/ec2-ai-coaching && git pull origin main && docker-compose down && docker-compose build --no-cache && docker-compose up -d && sleep 30 && echo "Deployment complete!" && docker-compose ps

Expected: All services "Up"


🔍 VERIFY DEPLOYMENT:
================================================================================

# Check all services running
docker-compose ps

# Check health endpoint
curl -s http://localhost:8001/health | python3 -m json.tool

# Verify Groq connection
docker-compose logs api | grep -i "groq\|phase 5" | tail -5

# Expected output: "Groq API is reachable" ✅


🤖 TEST TELEGRAM BOT:
================================================================================

1. Open Telegram
2. Search for your bot
3. Send: /start
4. Complete registration
5. Ask coaching question
6. Verify response (should be <2 seconds, Groq is fast!)


📊 MONITOR & TROUBLESHOOT:
================================================================================

# View all logs
docker-compose logs -f api

# View only Groq-related logs
docker-compose logs api | grep -i "groq"

# View health status
docker-compose logs api | grep -i "healthy"

# Check database users
docker-compose exec -T postgres psql -U postgres -c "SELECT COUNT(*) FROM users;"

# Check Redis
docker-compose exec redis redis-cli INFO


🔄 RESTART SERVICES:
================================================================================

# Restart just API (after code change)
docker-compose restart api

# Restart all services
docker-compose restart

# Rebuild API image
docker-compose build --no-cache api
docker-compose up -d api


📝 MANAGE USERS:
================================================================================

# List all users
docker-compose exec -T postgres psql -U postgres -c "SELECT id, name, email, telegram_chat_id FROM users;"

# Count users
docker-compose exec -T postgres psql -U postgres -c "SELECT COUNT(*) FROM users;"

# Delete all users (start fresh)
docker-compose exec -T postgres psql -U postgres -c "TRUNCATE TABLE users CASCADE; ALTER SEQUENCE users_id_seq RESTART WITH 1;"

# Delete specific user
docker-compose exec -T postgres psql -U postgres -c "DELETE FROM users WHERE id = 1;"


💾 BACKUP & RESTORE:
================================================================================

# Create manual backup
bash scripts/backup-to-s3.sh

# List backups
aws s3 ls s3://veda-ai-backups-*/production/postgresql/

# Restore from backup
bash scripts/restore-from-s3.sh <backup-filename>


🔧 CONFIGURATION CHANGES:
================================================================================

# Edit environment variables
nano .env

# Edit docker-compose
nano docker-compose.yml

# After editing:
docker-compose down
docker-compose up -d


📈 PERFORMANCE MONITORING:
================================================================================

# Check latencies
curl -s http://localhost:8001/health | python3 -m json.tool | grep -i "latency"

# Docker stats (memory, CPU)
docker stats --no-stream

# Check disk usage
df -h /

# Check database size
docker-compose exec postgres psql -U postgres -c "SELECT pg_size_pretty(pg_database_size('postgres'));"


❌ TROUBLESHOOTING:
================================================================================

# Containers not starting?
docker-compose logs | grep -i "error\|failed"

# Port conflicts?
lsof -i :8001  # Check if port in use

# Database connection error?
docker-compose logs postgres | grep -i "error"

# Groq API not responding?
curl -s http://localhost:8001/health | jq '.components.groq_connection'

# Telegram bot not responding?
docker-compose logs api | grep -i "telegram"


🔐 SECURITY CHECK:
================================================================================

# Verify HTTPS
curl -I https://vedaactivewellness.xyz

# Check firewall
sudo ufw status

# View security logs
sudo tail -n 50 /var/log/auth.log


🚨 EMERGENCY COMMANDS:
================================================================================

# Stop all services
docker-compose down

# Force restart all (nuclear option)
docker-compose down && docker system prune -a -f && docker-compose build --no-cache && docker-compose up -d

# Clear Docker resources
docker system prune -a --volumes -f

# View system resources
docker system df


📱 TELEGRAM BOT COMMANDS:
================================================================================

Commands available to users:

/start          - Register new user
/profile        - View your profile
/help           - Show all commands
/stats          - View coaching stats
/coach          - Get coaching response


🔑 GROQ API CONFIGURATION:
================================================================================

Current settings in .env:

OPENAI_API_KEY=gsk_...               ← Your Groq API key
OPENAI_BASE_URL=https://api.groq.com/openai/v1  ← Groq endpoint
GROQ_MODEL=mixtral-8x7b-32768       ← Default model

Available models:
- mixtral-8x7b-32768 (DEFAULT - recommended)
- llama2-70b-4096
- gemma-7b-it

To switch models, edit .env and restart:
docker-compose restart api


📊 SYSTEM HEALTH:
================================================================================

Quick status check:
docker-compose ps && echo "---" && curl -s http://localhost:8001/health | jq '.status'

Expected: All containers "Up" and status "healthy"


🎯 SUCCESS INDICATORS:
================================================================================

✅ All containers running: docker-compose ps shows all "Up"
✅ API health: curl shows "healthy"
✅ Groq working: logs show "Groq API is reachable"
✅ Bot responding: /start works in Telegram
✅ Response time: <2 seconds
✅ Database working: can see users in database


================================================================================
Need help? Check:
- GROQ_PRODUCTION_DEPLOYMENT.md (detailed guide)
- GROQ_FINAL_DEPLOYMENT_SUMMARY.md (full summary)
- docker-compose logs (error details)
- https://console.groq.com (Groq dashboard)

Status: ✅ PRODUCTION READY
================================================================================
