# INCIDENT RESPONSE RUNBOOK - Veda AI Coaching

## Quick Reference

| Incident | Impact | Resolution Time | Contact |
|----------|--------|-----------------|---------|
| API Down | Critical | < 5 min | On-call engineer |
| Database Down | Critical | < 10 min | DBA + On-call |
| High Error Rate | High | < 10 min | Platform team |
| Performance Degradation | Medium | < 30 min | Performance engineer |
| Disk Space Low | Medium | < 30 min | Infrastructure team |
| Memory Leak | Medium | < 1 hour | Backend engineer |
| SSL Certificate Expiry | Low | < 24 hours | Infrastructure team |

---

## INCIDENT 1: API Service Down

### Detection
- Health check returns `"status": "degraded"` or no response
- Error rate > 50%
- Application logs show startup failures

### Immediate Actions (0-5 minutes)

1. **Confirm Status**:
   ```bash
   curl -I https://vedaactivewellness.xyz/health
   # Should return HTTP 200
   
   docker-compose ps
   # Check if api container is running
   ```

2. **Collect Logs**:
   ```bash
   docker-compose logs --tail=100 api > /tmp/api_error.log
   cat /tmp/api_error.log | grep -i "error\|critical\|exception"
   ```

3. **Check Resource Constraints**:
   ```bash
   docker stats api
   # Is it OOM killed? High CPU?
   
   df -h /
   # Is disk full?
   ```

### Root Cause Analysis (5-15 minutes)

**If OOM (Out of Memory)**:
```bash
# Increase memory limit in docker-compose.yml
# Restart
docker-compose down
docker-compose up -d api

# Monitor
watch -n 1 'docker stats api'
```

**If Port Already in Use**:
```bash
lsof -i :8001
# Kill the process
kill -9 <PID>

# Restart
docker-compose restart api
```

**If Database Connection Failed**:
```bash
docker-compose logs postgres
# Check if postgres is healthy
docker-compose exec postgres pg_isready
```

**If Secrets/Config Missing**:
```bash
docker-compose logs api | grep -i "env\|config\|missing"
# Verify .env file exists and has all required variables
cat .env | grep -c "="  # Should be > 20
```

### Recovery Steps

```bash
# Step 1: Stop all services
docker-compose down

# Step 2: Backup current state
docker-compose logs > /tmp/api_down_$(date +%s).log

# Step 3: Check for corruption
docker-compose exec postgres psql -U postgres -c "SELECT 1"

# Step 4: Rebuild if needed
docker-compose build --no-cache api

# Step 5: Start services
docker-compose up -d

# Step 6: Monitor startup
docker-compose logs -f api | head -20

# Step 7: Verify health
sleep 30
curl https://vedaactivewellness.xyz/health | jq '.status'
```

### Post-Incident

- [ ] Document root cause
- [ ] Create alert for early detection
- [ ] Schedule capacity review if memory issue
- [ ] Update runbook with findings

---

## INCIDENT 2: Database Connection Pool Exhausted

### Detection
- Health check shows `postgres: unhealthy`
- Logs: `"too many connections"` or `"FATAL: remaining connection slots reserved"`
- API response time spikes

### Immediate Actions

1. **Check Connection Count**:
   ```bash
   docker-compose exec postgres psql -U postgres -c \
     "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"
   ```

2. **List Active Connections**:
   ```bash
   docker-compose exec postgres psql -U postgres -c \
     "SELECT pid, usename, state FROM pg_stat_activity WHERE state != 'idle';"
   ```

3. **Increase Pool Size** (if not at max):
   ```bash
   # Edit backend/database.py
   DB_POOL_SIZE = 40  # Increase from 20
   DB_MAX_OVERFLOW = 80  # Increase from 40
   
   # Rebuild and restart
   docker-compose build api
   docker-compose up -d api
   ```

### Root Cause Analysis

**Common Causes**:
- Connection leaks in application code
- Too many Celery workers connecting
- Slow queries blocking connections
- Replica database configuration issue

### Recovery

```bash
# Option 1: Kill idle connections
docker-compose exec postgres psql -U postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';"

# Option 2: Restart PostgreSQL
docker-compose restart postgres
docker-compose logs -f postgres | head -20

# Option 3: Full reset (if corrupted)
# Create backup first!
bash scripts/backup-to-s3.sh

# Drop all connections and restart
docker-compose exec postgres psql -U postgres -c \
  "ALTER DATABASE postgres ALLOW_CONNECTIONS FALSE;"
docker-compose exec postgres psql -U postgres -c \
  "ALTER DATABASE postgres ALLOW_CONNECTIONS TRUE;"

docker-compose restart postgres
```

---

## INCIDENT 3: High Error Rate (> 10%)

### Detection
- CloudWatch alarm triggered
- Dashboard shows red zone
- User reports: "Application is broken"

### Immediate Actions

1. **Check Error Types**:
   ```bash
   docker-compose logs api | grep -i "error\|exception" | tail -50
   
   # Group by error type
   docker-compose logs api | grep -i "error" | awk -F: '{print $NF}' | sort | uniq -c
   ```

2. **Check Recent Deployments**:
   ```bash
   git log --oneline -10
   # Was something deployed recently?
   ```

3. **Monitor in Real-time**:
   ```bash
   watch -n 5 'curl -s https://vedaactivewellness.xyz/health | jq ".components"'
   ```

### Root Cause Analysis

**Rate Limiting Triggered**:
```bash
docker-compose logs api | grep "Rate limit exceeded"
# Check if under DDoS or load test is running
```

**Celery Task Failures**:
```bash
docker-compose logs celery_worker | grep "FAILED\|ERROR"
```

**Database Issues**:
```bash
docker-compose exec postgres psql -U postgres -c \
  "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

**OpenAI API Down**:
```bash
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | jq '.data | length'
# If 0, OpenAI is down
```

### Recovery

```bash
# Option 1: Identify bad code and rollback
git revert <commit-hash>
docker-compose build api
docker-compose up -d api

# Option 2: Kill stuck tasks
docker-compose exec celery_worker celery -A backend.celery_app purge

# Option 3: Increase resources
# Edit docker-compose.yml, increase limits
docker-compose up -d

# Option 4: Enable maintenance mode
# Redirect traffic to static maintenance page
# (Configure in Caddy or frontend)
```

---

## INCIDENT 4: Disk Space Critical (< 5%)

### Detection
- CloudWatch alarm: `"DiskSpace < 10%"`
- Logs stop being written
- New deployments fail

### Immediate Actions

1. **Check Disk Usage**:
   ```bash
   df -h /
   du -sh /var/lib/docker/* 2>/dev/null | sort -h
   du -sh * 2>/dev/null | sort -h
   ```

2. **Identify Large Files**:
   ```bash
   find / -type f -size +100M 2>/dev/null | head -20
   ```

3. **Clean Docker**:
   ```bash
   # Remove unused containers
   docker container prune -f
   
   # Remove unused images
   docker image prune -a -f
   
   # Remove unused volumes
   docker volume prune -f
   
   # Check cleanup results
   df -h /
   ```

4. **Clean Application Logs**:
   ```bash
   # Rotate logs
   sudo logrotate -f /etc/logrotate.d/veda-ai-coaching
   
   # Clear docker logs
   docker-compose logs --help | grep -i tail
   ```

### Root Cause Analysis

**Database Growing Too Fast**:
```bash
docker-compose exec postgres psql -U postgres -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"

# Delete old data if needed
docker-compose exec postgres psql -U postgres -c \
  "DELETE FROM activities WHERE created_at < NOW() - INTERVAL '90 days';"
```

**Cache/Temp Files**:
```bash
# Clear Redis
docker-compose exec redis redis-cli FLUSHALL

# Clear tmp
rm -rf /tmp/*
```

### Prevention

```bash
# Set automatic cleanup
# Edit docker-compose.yml logging section (already done)
# Logs are rotated to max 50m per file, max 3 files

# Setup disk usage alerts
aws cloudwatch put-metric-alarm \
  --alarm-name disk-space-critical \
  --threshold 5 \
  --comparison-operator LessThanThreshold
```

---

## INCIDENT 5: Celery Workers Not Processing Tasks

### Detection
- Tasks stay in "PENDING" state
- No logs from celery_worker
- Backlog growing

### Immediate Actions

1. **Check Worker Status**:
   ```bash
   docker-compose exec celery_worker celery -A backend.celery_app inspect ping
   # Should show worker is alive
   
   docker-compose exec celery_worker celery -A backend.celery_app inspect active
   # Should show active tasks
   ```

2. **Check Redis Connection**:
   ```bash
   docker-compose exec redis redis-cli ping
   # Should return PONG
   
   docker-compose exec redis redis-cli DBSIZE
   # Should show number of tasks queued
   ```

3. **Check Worker Logs**:
   ```bash
   docker-compose logs celery_worker | grep -i "error\|failed\|exception" | tail -20
   ```

### Recovery

```bash
# Option 1: Restart worker
docker-compose restart celery_worker
docker-compose logs -f celery_worker | head -20

# Option 2: Purge stuck tasks
docker-compose exec celery_worker celery -A backend.celery_app purge
# WARNING: This deletes all pending tasks!

# Option 3: Increase concurrency
# Edit docker-compose.yml celery_worker command
# Change --concurrency=4 to --concurrency=8
docker-compose up -d celery_worker

# Option 4: Check for deadlock
docker-compose exec postgres psql -U postgres -c "SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE state LIKE '%deadlock%';"
```

---

## INCIDENT 6: SSL Certificate Expiry

### Detection
- Browser shows security warning
- Health check: `"SSL certificate problem"`
- Days until expiry < 7

### Immediate Actions

1. **Check Certificate Status**:
   ```bash
   echo | openssl s_client -servername vedaactivewellness.xyz -connect vedaactivewellness.xyz:443 2>/dev/null | \
     openssl x509 -noout -dates
   ```

2. **Check Caddy Logs**:
   ```bash
   docker-compose logs caddy | grep -i "cert\|error" | tail -20
   ```

3. **Force Renewal**:
   ```bash
   docker-compose exec caddy caddy reload
   # Caddy auto-renews Let's Encrypt certs
   ```

### Prevention

- Caddy automatically renews 30 days before expiry
- Monitor via CloudWatch alerts set to trigger at 7 days before expiry

---

## INCIDENT 7: Performance Degradation

### Detection
- p99 latency > 1000ms
- API response times increasing over time
- User reports: "Application is slow"

### Immediate Actions

1. **Check System Resources**:
   ```bash
   docker stats --no-stream
   
   free -h  # Memory
   df -h    # Disk
   uptime   # CPU load
   ```

2. **Identify Slow Queries**:
   ```bash
   docker-compose exec postgres psql -U postgres -c \
     "SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
   ```

3. **Check Application Metrics**:
   ```bash
   curl -s https://vedaactivewellness.xyz/health/metrics | jq '.latency_percentiles'
   ```

### Root Cause Analysis

**Connection Pool Contention**:
```bash
docker-compose exec postgres psql -U postgres -c \
  "SELECT count(*) FROM pg_stat_activity;"
# If near max_connections, increase pool size
```

**Slow Queries**:
```bash
# Enable query logging
docker-compose exec postgres psql -U postgres -c \
  "ALTER DATABASE postgres SET log_min_duration_statement = 1000;"
# Restart postgres
docker-compose restart postgres
```

**Memory Leak**:
```bash
# Monitor memory over time
watch -n 10 'docker stats api --no-stream'
# If steadily increasing, rebuild api
docker-compose build --no-cache api
docker-compose up -d api
```

### Recovery

```bash
# Option 1: Increase resources
# Edit docker-compose.yml resource limits
docker-compose up -d

# Option 2: Scale horizontally (if using load balancer)
docker-compose up -d --scale api=3

# Option 3: Optimize queries
# Profile with pg_stat_statements
# Add indexes for frequent queries
```

---

## Escalation Path

**Severity Levels**:
- **P1 (Critical)**: System down, data loss, security breach
  - Escalate to: VP Engineering + On-call team
  - Response time: < 15 minutes
  
- **P2 (High)**: Significant functionality broken, performance severely degraded
  - Escalate to: Engineering Lead + On-call
  - Response time: < 1 hour
  
- **P3 (Medium)**: Minor functionality issues, slow performance
  - Escalate to: Team Lead
  - Response time: < 4 hours
  
- **P4 (Low)**: Documentation issues, minor bugs
  - No escalation needed
  - Resolution: Next sprint

---

## Post-Incident Checklist

- [ ] Root cause identified and documented
- [ ] Temporary fix implemented (if needed)
- [ ] Permanent fix created and tested
- [ ] Monitoring/alerting rules updated
- [ ] Related runbooks updated
- [ ] Team post-mortem scheduled
- [ ] Prevention measures implemented
- [ ] Customer communications sent (if applicable)

---

## Contact Information

| Role | Name | Phone | Email |
|------|------|-------|-------|
| On-Call | [Name] | [Phone] | [Email] |
| Engineering Lead | [Name] | [Phone] | [Email] |
| VP Engineering | [Name] | [Phone] | [Email] |
| AWS Support | - | +1-206-xxx-xxxx | support@aws.com |

---

**Last Updated**: December 2024  
**Version**: 1.0  
**Approval**: [Engineering Lead]
