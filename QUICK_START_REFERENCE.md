# ⚡ QUICK START REFERENCE CARD

## 45-Minute Deployment

```bash
# 1. SSH to EC2
ssh -i coaching.pem ubuntu@13.233.127.186

# 2. Setup
cd ~ && git clone <repo> veda-ai-coaching && cd veda-ai-coaching

# 3. Security Hardening (5 min)
bash scripts/ec2-security-hardening.sh

# 4. Docker Install (if needed)
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker ubuntu && newgrp docker

# 5. Configure Secrets (5 min)
cp .env.example .env
nano .env  # Fill in: DATABASE_PASSWORD, API_KEYS, etc.
chmod 600 .env

# 6. Deploy (15 min)
docker-compose build
docker-compose up -d
sleep 40  # Wait for initialization

# 7. Verify (2 min)
curl https://vedaactivewellness.xyz/health | jq '.status'
# Output should be: "healthy"

# 8. Setup Monitoring (5 min)
bash scripts/setup-cloudwatch-monitoring.sh

# 9. Schedule Backups (1 min)
(crontab -l 2>/dev/null; echo "0 2 * * * cd ~/veda-ai-coaching && bash scripts/backup-to-s3.sh") | crontab -

# 10. Validate (5 min)
bash scripts/production-validation.sh
# Should see: ✓ PRODUCTION READY

# ✅ YOU'RE LIVE!
```

---

## 📋 REQUIRED ENVIRONMENT VARIABLES

```bash
# Secrets from AWS Secrets Manager
POSTGRES_PASSWORD=<STRONG_PASSWORD>
DATABASE_URL=postgresql://postgres:[REDACTED]@postgres:5432/postgres

# API Keys (obtain from provider)
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
STRAVA_CLIENT_SECRET=...

# Configuration
ENVIRONMENT=production
DOMAIN=vedaactivewellness.xyz
AWS_REGION=ap-south-1
S3_BACKUP_BUCKET=veda-ai-backups-xxxxx
```

---

## 🚨 EMERGENCY COMMANDS

| Issue | Command |
|-------|---------|
| API down | `docker-compose restart api` |
| Database down | `docker-compose restart postgres` |
| Check health | `curl http://localhost:8001/health \| jq` |
| View logs | `docker-compose logs -f api` |
| Backup now | `bash scripts/backup-to-s3.sh` |
| Restore DB | `bash scripts/restore-from-s3.sh <filename>` |
| Disk full | `docker system prune -a -f` |
| High CPU | `docker stats` |
| All containers | `docker-compose ps` |

---

## ✅ PRE-GO-LIVE CHECKLIST

- [ ] DNS A record → 13.233.127.186
- [ ] .env configured with all secrets
- [ ] docker-compose up -d succeeded
- [ ] Health endpoint returns "healthy"
- [ ] SSL certificate auto-provisioned (Caddy)
- [ ] CloudWatch dashboard created
- [ ] Backup test successful
- [ ] Rate limiting verified (150 req/min → 429 errors)
- [ ] validation script passed
- [ ] Team notified of deployment

---

## 📊 MONITORING DASHBOARD

**Access**: https://console.aws.amazon.com/cloudwatch/  
**Dashboard**: veda-ai-coaching-production

**Alarms Created**:
- ✓ CPU > 80%
- ✓ Memory > 85%
- ✓ Disk < 10%
- ✓ API latency p99 > 1s
- ✓ DB queries > 5s
- ✓ Health check failed

---

## 🔄 COMMON OPERATIONS

### View Logs
```bash
docker-compose logs -f api          # API logs
docker-compose logs -f celery_worker # Celery logs
docker-compose logs -f postgres      # Database logs
```

### Restart Services
```bash
docker-compose restart api           # Just API
docker-compose restart               # All services
```

### Database Access
```bash
docker-compose exec postgres psql -U postgres
# Commands: \dt (tables), \db (backups), \q (exit)
```

### Backup & Restore
```bash
bash scripts/backup-to-s3.sh        # Create backup
bash scripts/restore-from-s3.sh     # Restore from S3
aws s3 ls s3://bucket/path/         # List backups
```

### Update Application
```bash
git pull origin main
docker-compose build api
docker-compose up -d api
```

---

## 🎯 SUCCESS METRICS (24 Hours)

| Metric | Target | Check |
|--------|--------|-------|
| Uptime | 100% | `curl /health` |
| p99 Latency | < 1s | CloudWatch dashboard |
| Error Rate | < 1% | CloudWatch logs |
| Backup Status | Success | S3 console |
| CPU Usage | < 40% | CloudWatch metrics |
| Memory Usage | < 60% | CloudWatch metrics |
| Disk Usage | < 50% | CloudWatch metrics |
| Alarms Triggered | 0 | CloudWatch alarms |

---

## 📞 SUPPORT

- **Status**: Health dashboard: https://vedaactivewellness.xyz/health
- **Monitoring**: CloudWatch: https://console.aws.amazon.com/cloudwatch/
- **Logs**: `docker-compose logs` or CloudWatch log group
- **Database**: Direct PostgreSQL access via Docker
- **Backups**: AWS S3 console or restore script

---

**Version**: 4.2.0  
**Status**: ✅ READY FOR PRODUCTION  
**Updated**: December 2024

🚀 **Deploy with confidence. You've got this!**
