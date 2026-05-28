# 🚀 COMPLETE EC2 PRODUCTION DEPLOYMENT GUIDE - 100% READY

## Prerequisites

- **EC2 Instance**: Ubuntu 22.04 LTS, t3.large or better
- **IP Address**: 13.233.127.186
- **Domain**: vedaactivewellness.xyz (DNS A record pointing to EC2 IP)
- **SSH Key**: coaching.pem (stored securely)
- **AWS Credentials**: With access to S3, CloudWatch, Secrets Manager
- **Required API Keys**: OpenAI, Telegram, Strava (already obtained)

---

## ✅ DEPLOYMENT CHECKLIST

### Phase 1: EC2 Instance Preparation (10 minutes)

- [ ] **SSH Access**: Test connection
  ```bash
  ssh -i "path/to/coaching.pem" ubuntu@13.233.127.186
  ```

- [ ] **System Update**:
  ```bash
  sudo apt-get update && sudo apt-get upgrade -y
  ```

- [ ] **Install Docker & Docker Compose**:
  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
  sudo apt-get install -y docker-compose-plugin
  sudo usermod -aG docker ubuntu
  newgrp docker
  docker --version
  ```

- [ ] **Install Git**:
  ```bash
  sudo apt-get install -y git
  ```

- [ ] **Clone Repository**:
  ```bash
  cd ~
  git clone <your-repo-url> veda-ai-coaching
  cd veda-ai-coaching
  ```

### Phase 2: Security Hardening (5 minutes)

- [ ] **Run Security Hardening Script**:
  ```bash
  chmod +x scripts/ec2-security-hardening.sh
  ./scripts/ec2-security-hardening.sh
  ```

- [ ] **Configure SSH Key-Based Auth Only**:
  ```bash
  # From local machine:
  ssh-copy-id -i "path/to/coaching.pem" ubuntu@13.233.127.186
  
  # SSH in and verify no password auth
  ssh -i "path/to/coaching.pem" ubuntu@13.233.127.186
  ```

- [ ] **Create Application User**:
  ```bash
  sudo useradd -m -s /bin/bash -G docker veda
  sudo mkdir -p /home/veda/.ssh
  sudo chmod 700 /home/veda/.ssh
  ```

- [ ] **Test Firewall Rules**:
  ```bash
  sudo ufw status
  # Should show: 22/tcp, 80/tcp, 443/tcp ALLOW
  ```

### Phase 3: AWS Setup (10 minutes)

- [ ] **Create IAM Role for EC2**:
  ```
  1. AWS Console → IAM → Roles → Create Role
  2. Service: EC2
  3. Attach policies:
     - AmazonSSMManagedInstanceCore
     - CloudWatchAgentServerPolicy
     - AmazonS3FullAccess
  4. Role name: VedaAICoachingEC2Role
  5. Attach to running EC2 instance
  ```

- [ ] **Create S3 Bucket for Backups**:
  ```bash
  aws s3 mb s3://veda-ai-backups-$(date +%s) --region ap-south-1
  # Note the bucket name for .env
  ```

- [ ] **Create AWS Secrets Manager Secret**:
  ```bash
  aws secretsmanager create-secret \
    --name /veda-ai-coaching/production \
    --region ap-south-1 \
    --secret-string '{
      "DATABASE_PASSWORD": "YOUR_STRONG_PASSWORD",
      "POSTGRES_PASSWORD": "YOUR_STRONG_PASSWORD",
      "OPENAI_API_KEY": "sk-...",
      "TELEGRAM_BOT_TOKEN": "...",
      "STRAVA_CLIENT_SECRET": "..."
    }'
  ```

### Phase 4: Environment Configuration (10 minutes)

- [ ] **Create Production .env**:
  ```bash
  cd ~/veda-ai-coaching
  cp .env.example .env
  nano .env
  ```

  **Fill in these values**:
  ```bash
  # Database
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=<STRONG_PASSWORD_FROM_SECRETS_MANAGER>
  DATABASE_URL=postgresql://postgres:<STRONG_PASSWORD>@postgres:5432/postgres
  
  # Redis
  REDIS_URL=redis://redis:6379/0
  
  # Environment
  ENVIRONMENT=production
  DOMAIN=vedaactivewellness.xyz
  ALLOWED_ORIGIN=https://vedaactivewellness.xyz
  FRONTEND_API_URL=https://vedaactivewellness.xyz
  LOG_LEVEL=info
  
  # API Keys (from Secrets Manager or .env.prod)
  OPENAI_API_KEY=sk-...
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_SECRET_TOKEN=...
  STRAVA_CLIENT_ID=204777
  STRAVA_CLIENT_SECRET=...
  STRAVA_SIGNING_SECRET=...
  STRAVA_REDIRECT_URI=https://vedaactivewellness.xyz/auth/callback
  ADMIN_API_KEY=<GENERATE_STRONG_KEY>
  
  # AWS
  AWS_REGION=ap-south-1
  S3_BACKUP_BUCKET=veda-ai-backups-xxxxx
  
  # Optional
  SENTRY_DSN=
  ```

- [ ] **Verify .env is NOT committed to git**:
  ```bash
  grep "^.env$" .gitignore  # Should output .env
  ```

- [ ] **Secure .env Permissions**:
  ```bash
  chmod 600 .env
  sudo chown veda:veda .env
  ```

### Phase 5: Docker Deployment (15 minutes)

- [ ] **Build Docker Images**:
  ```bash
  docker-compose build
  # Takes ~5-10 minutes
  ```

- [ ] **Start Services in Background**:
  ```bash
  docker-compose up -d
  ```

- [ ] **Wait for Initialization** (30-40 seconds):
  ```bash
  docker-compose logs -f api | grep "DATABASE INITIALIZATION COMPLETED"
  ```

- [ ] **Verify All Services Running**:
  ```bash
  docker-compose ps
  # All services should show "Up" status
  ```

- [ ] **Check Health Endpoint**:
  ```bash
  curl http://localhost:8001/health | jq .
  # Should return: "status": "healthy"
  ```

- [ ] **View Application Logs**:
  ```bash
  docker-compose logs --tail=50 api
  docker-compose logs --tail=50 celery_worker
  docker-compose logs --tail=50 postgres
  ```

### Phase 6: DNS & SSL Configuration (5 minutes)

- [ ] **Verify Domain Routing**:
  ```bash
  # Check DNS A record points to 13.233.127.186
  dig vedaactivewellness.xyz
  nslookup vedaactivewellness.xyz
  ```

- [ ] **Wait for SSL Certificate** (Caddy auto-provisioning):
  ```bash
  sleep 30
  curl https://vedaactivewellness.xyz/health
  # Should return: "status": "healthy"
  ```

- [ ] **Test All Endpoints**:
  ```bash
  # Frontend
  curl -I https://vedaactivewellness.xyz
  
  # API
  curl https://vedaactivewellness.xyz/api/stats
  
  # Health
  curl https://vedaactivewellness.xyz/health | jq .
  ```

### Phase 7: Backup & Monitoring Setup (10 minutes)

- [ ] **Test Backup Script**:
  ```bash
  chmod +x scripts/backup-to-s3.sh
  bash scripts/backup-to-s3.sh
  # Verify backup in S3
  aws s3 ls s3://veda-ai-backups-xxxxx/production/postgresql/
  ```

- [ ] **Setup Automated Backups** (via cron):
  ```bash
  # Daily backup at 2 AM UTC
  (crontab -l 2>/dev/null; echo "0 2 * * * cd ~/veda-ai-coaching && bash scripts/backup-to-s3.sh >> /tmp/backup.log 2>&1") | crontab -
  ```

- [ ] **Setup CloudWatch Monitoring**:
  ```bash
  chmod +x scripts/setup-cloudwatch-monitoring.sh
  ./scripts/setup-cloudwatch-monitoring.sh
  ```

- [ ] **Install CloudWatch Agent**:
  ```bash
  # Download config and install
  # (See CloudWatch agent setup docs)
  ```

### Phase 8: Production Verification (10 minutes)

- [ ] **Test All Public Endpoints**:
  ```bash
  # Health check
  curl -s https://vedaactivewellness.xyz/health | jq .
  
  # API endpoints
  curl -s https://vedaactivewellness.xyz/api/stats | jq .
  curl -s https://vedaactivewellness.xyz/api/activities | jq .
  
  # Frontend
  curl -I https://vedaactivewellness.xyz | grep -i "content-type"
  ```

- [ ] **Verify Rate Limiting**:
  ```bash
  # Run 150 requests rapidly (should hit 429 after 100)
  for i in {1..150}; do 
    curl -s -w "%{http_code}\n" -o /dev/null https://vedaactivewellness.xyz/ping
  done | sort | uniq -c
  ```

- [ ] **Check Database Tables**:
  ```bash
  docker-compose exec postgres psql -U postgres -c "\dt"
  # Should show: users, activities, coach_memory, etc.
  ```

- [ ] **Verify pgvector**:
  ```bash
  docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_extension WHERE extname = 'pgvector';"
  # Should return one row with pgvector
  ```

- [ ] **Check Celery Workers**:
  ```bash
  docker-compose logs celery_worker | grep "OK"
  # Should see: "celery@... ready"
  ```

- [ ] **Test Backup/Restore**:
  ```bash
  # Create test backup
  bash scripts/backup-to-s3.sh
  
  # Verify it's in S3
  aws s3 ls s3://veda-ai-backups-xxxxx/production/postgresql/ --recursive
  ```

- [ ] **Check Logs for Errors**:
  ```bash
  docker-compose logs | grep -i "error"
  # Should have no critical errors
  ```

### Phase 9: Monitoring & Alerting (5 minutes)

- [ ] **Configure CloudWatch Dashboard**:
  Visit: https://console.aws.amazon.com/cloudwatch/home
  - View "veda-ai-coaching-production" dashboard
  - Monitor CPU, Memory, Disk, API latency

- [ ] **Setup SNS for Alerts**:
  ```bash
  # Create SNS topic
  aws sns create-topic --name veda-ai-alerts --region ap-south-1
  
  # Subscribe to email/Slack
  aws sns subscribe --topic-arn arn:aws:sns:ap-south-1:ACCOUNT:veda-ai-alerts \
    --protocol email --notification-endpoint your-email@example.com
  ```

- [ ] **Update Alarm Notifications**:
  Add SNS topic ARN to each CloudWatch alarm

### Phase 10: Go Live (2 minutes)

- [ ] **Final Health Check**:
  ```bash
  curl -s https://vedaactivewellness.xyz/health | jq '.status'
  # Should return: "healthy"
  ```

- [ ] **Send Test Notification**:
  ```bash
  # Send test message through Telegram
  curl -X POST https://vedaactivewellness.xyz/webhook/telegram \
    -H "Content-Type: application/json" \
    -d '{"message": "Deployment successful!"}'
  ```

- [ ] **Record Backup Location**:
  ```bash
  echo "S3 Backups: s3://veda-ai-backups-xxxxx/production/postgresql/"
  echo "Backup script: ~/veda-ai-coaching/scripts/backup-to-s3.sh"
  echo "Restore script: ~/veda-ai-coaching/scripts/restore-from-s3.sh"
  ```

- [ ] **✅ DEPLOYMENT COMPLETE**

---

## 🔒 Security Best Practices

1. **Secrets Management**: Never commit .env to git
2. **SSH Only**: Disable password authentication
3. **Backups**: Daily to S3 with 30-day retention
4. **Monitoring**: 24/7 CloudWatch alerts
5. **Updates**: Automatic security patches enabled
6. **Firewall**: Only ports 22, 80, 443 open
7. **Logs**: Retained for 30 days in CloudWatch
8. **SSL/TLS**: Auto-renewed by Caddy

---

## 📊 Monitoring Commands

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f celery_worker
docker-compose logs -f postgres

# Check container stats
docker stats

# Health check
curl https://vedaactivewellness.xyz/health | jq .

# Database stats
docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_stat_statements LIMIT 10;"

# Redis stats
docker-compose exec redis redis-cli INFO

# Celery workers
docker exec celery_worker celery -A backend.celery_app inspect active

# Check backups
aws s3 ls s3://veda-ai-backups-xxxxx/production/postgresql/ --recursive --human-readable
```

---

## 🚨 Incident Response

### If Health Check Fails

```bash
# Check which service is down
curl http://localhost:8001/health | jq '.components'

# If PostgreSQL down
docker-compose restart postgres
docker-compose logs -f postgres

# If Redis down
docker-compose restart redis

# If API down
docker-compose restart api
docker-compose logs -f api
```

### If Disk Space Low

```bash
# Check disk usage
df -h

# Clean Docker images/containers
docker system prune -a

# Remove old logs
docker-compose exec postgres vacuumdb -U postgres
```

### If Database Corrupted

```bash
# Restore from backup
bash scripts/restore-from-s3.sh <backup-filename>
```

---

## 🔄 Upgrade Process

```bash
# 1. Stop services
docker-compose down

# 2. Backup database
bash scripts/backup-to-s3.sh

# 3. Pull new code
git pull origin main

# 4. Build new images
docker-compose build

# 5. Start services
docker-compose up -d

# 6. Verify
curl https://vedaactivewellness.xyz/health | jq .
```

---

## 📞 Support Resources

- **Health Dashboard**: https://vedaactivewellness.xyz/health
- **CloudWatch**: https://console.aws.amazon.com/cloudwatch/
- **Application Logs**: `docker-compose logs -f`
- **Database**: `docker-compose exec postgres psql -U postgres`
- **Backups**: `aws s3 ls s3://veda-ai-backups-xxxxx/production/postgresql/`

---

**Deployment Date**: [Date]  
**Version**: 4.2.0 (100% Production Ready)  
**Status**: ✅ Live and Monitoring
