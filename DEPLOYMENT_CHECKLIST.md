# ✅ EC2 AI Coaching - Production Deployment Checklist

## Pre-Deployment Phase

### Environment Setup
- [ ] Copy `.env.example` to `.env`
- [ ] Fill in `DATABASE_URL` with PostgreSQL credentials
- [ ] Fill in `REDIS_URL` with Redis connection
- [ ] Fill in `OPENAI_API_KEY`
- [ ] Fill in `TELEGRAM_BOT_TOKEN`
- [ ] Fill in `TELEGRAM_SECRET_TOKEN`
- [ ] Fill in `STRAVA_CLIENT_ID`
- [ ] Fill in `STRAVA_CLIENT_SECRET`
- [ ] Fill in `STRAVA_SIGNING_SECRET`
- [ ] Fill in `STRAVA_REDIRECT_URI`
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `LOG_LEVEL=info` or `warning`

### File Verification
- [ ] `docker-compose.yml` exists and uses pgvector image
- [ ] `backend/main.py` has lifespan context manager
- [ ] `backend/database.py` has initialize_database() function
- [ ] `backend/Dockerfile` is multi-stage
- [ ] `scripts/init_db.sql` exists
- [ ] `scripts/init_database.py` exists
- [ ] `.env.example` template exists
- [ ] `PRODUCTION_SETUP.md` documentation exists
- [ ] `UPGRADE_SUMMARY.md` documentation exists
- [ ] `validate_production.sh` script exists

### Code Quality
- [ ] No Python syntax errors: `python -m py_compile backend/main.py`
- [ ] No Python syntax errors: `python -m py_compile backend/database.py`
- [ ] No Python syntax errors: `python -m py_compile backend/celery_app.py`
- [ ] Docker-compose.yml is valid: `docker-compose config`
- [ ] All required functions exist in database.py:
  - [ ] `initialize_database()`
  - [ ] `wait_for_database()`
  - [ ] `ensure_pgvector_extension()`
  - [ ] `run_alembic_migrations()`
  - [ ] `create_all_tables()`
  - [ ] `health_check()`

### Automated Validation
- [ ] Run validation script: `bash validate_production.sh`
- [ ] All tests pass (0 failures)
- [ ] Docker image builds: `docker build -f backend/Dockerfile -t test .`
- [ ] Image size is reasonable (<1GB)

---

## Deployment Phase

### Pre-Deployment Backup
- [ ] Export current database: `pg_dump ... > backup_before_upgrade.sql`
- [ ] Copy backup to safe location
- [ ] Verify backup is readable

### Service Deployment
- [ ] Stop existing services: `docker-compose down`
- [ ] Build new images: `docker-compose build`
- [ ] Start services: `docker-compose up -d`
- [ ] Wait 40+ seconds for initialization

### Verify Initialization
- [ ] Check PostgreSQL logs: `docker-compose logs postgres | grep pgvector`
- [ ] Check API logs: `docker-compose logs api | grep "INITIALIZATION COMPLETED"`
- [ ] Check Redis is running: `docker-compose exec redis redis-cli ping`
- [ ] Check database tables exist: `docker-compose exec postgres psql -U postgres -c "\dt"`
- [ ] Verify pgvector extension: `docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_extension WHERE extname='pgvector'"`

---

## Verification Phase

### Health Checks
- [ ] API health endpoint: `curl http://localhost:8001/health | jq .status`
- [ ] Expected response: `"healthy"`
- [ ] Check all components healthy:
  - [ ] postgres: healthy
  - [ ] redis: healthy
  - [ ] database_tables: healthy
  - [ ] celery_workers: healthy (or waiting)
  - [ ] openai: healthy or configured

### Endpoint Testing
- [ ] Ping endpoint works: `curl http://localhost:8001/ping`
- [ ] Stats endpoint works: `curl http://localhost:8001/api/stats`
- [ ] Activities endpoint works: `curl http://localhost:8001/api/activities`
- [ ] No 500 errors in responses

### Database Verification
- [ ] Tables created:
  ```bash
  docker-compose exec postgres psql -U postgres -c \
    "SELECT COUNT(*) as table_count FROM information_schema.tables \
     WHERE table_schema='public';"
  ```
- [ ] Should show >0 tables
- [ ] Check critical tables:
  - [ ] users
  - [ ] activities
  - [ ] coach_memory
  - [ ] strava_tokens
  - [ ] daily_readiness

### Celery Verification
- [ ] Celery worker is running: `docker-compose ps celery_worker`
- [ ] Worker status: Up
- [ ] Check worker logs: `docker-compose logs celery_worker | grep "worker online"`
- [ ] Celery Beat is running: `docker-compose ps celery_beat`
- [ ] Beat status: Up

### Log Analysis
- [ ] Check for ERROR logs: `docker-compose logs | grep ERROR`
- [ ] Check for CRITICAL logs: `docker-compose logs | grep CRITICAL`
- [ ] Check for database connection errors: `docker-compose logs | grep "connection refused"`
- [ ] Check for Redis errors: `docker-compose logs | grep "redis_dependency"`
- [ ] No concerning warnings (⚠️ messages acceptable for optional features)

---

## Post-Deployment Phase

### 24-Hour Monitoring
- [ ] Monitor health every hour: `curl http://localhost:8001/health`
- [ ] Check logs for errors: `docker-compose logs | grep -i error`
- [ ] Verify Celery tasks are executing: `celery -A backend.celery_app inspect active`
- [ ] Check database disk usage: `docker-compose exec postgres df -h /var/lib/postgresql/data`
- [ ] Monitor API response times (should be <100ms)

### Data Integrity
- [ ] Verify user data: `docker-compose exec postgres psql -U postgres -c "SELECT COUNT(*) FROM users;"`
- [ ] Verify activities: `docker-compose exec postgres psql -U postgres -c "SELECT COUNT(*) FROM activities;"`
- [ ] Run test Celery task:
  ```bash
  celery -A backend.celery_app call backend.celery_app.debug_task
  ```
- [ ] Expected: Task completes successfully

### Performance Testing
- [ ] API response time <100ms: `time curl http://localhost:8001/health`
- [ ] Database query time <10ms: Verify in logs
- [ ] No connection pool exhaustion: Check pool stats
- [ ] Memory usage stable: `docker stats` every 5 minutes

### Backup Verification
- [ ] Automated backups configured (if using)
- [ ] First backup completed successfully
- [ ] Backup restore tested (optional but recommended)

---

## Rollback Procedures

### If Issues Occur (Choose One)

#### Option 1: Simple Restart
```bash
docker-compose restart api celery_worker celery_beat
```

#### Option 2: Recreate Services
```bash
docker-compose down
docker-compose up -d
```

#### Option 3: Full Rollback
```bash
# Stop new version
docker-compose down

# Restore database backup (if made)
docker-compose exec postgres psql -U postgres < backup_before_upgrade.sql

# Checkout previous version of files
git checkout HEAD~1 docker-compose.yml backend/main.py backend/database.py

# Start previous version
docker-compose up -d
```

---

## Issue Resolution Checklist

### Issue: pgvector not found
- [ ] Verify image is pgvector/pgvector:pg16-latest in docker-compose.yml
- [ ] Stop and remove postgres container: `docker-compose rm postgres`
- [ ] Start postgres again: `docker-compose up -d postgres`
- [ ] Wait 10 seconds and check: `docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_extension WHERE extname='pgvector';"`

### Issue: Tables don't exist
- [ ] Check API startup logs: `docker-compose logs api | grep "DATABASE INITIALIZATION"`
- [ ] If no initialization log: Check for errors in postgres logs
- [ ] Manual database initialization: `docker-compose exec api python scripts/init_database.py`
- [ ] Restart Celery: `docker-compose restart celery_worker`

### Issue: Celery tasks failing
- [ ] Check task error: `docker-compose logs celery_worker | grep ERROR`
- [ ] Common cause: "table does not exist" → Wait for API to initialize
- [ ] Common cause: Redis connection → Check Redis is running: `docker-compose ps redis`
- [ ] Common cause: Database connection → Check DATABASE_URL in .env

### Issue: Redis connection refused
- [ ] Check Redis is running: `docker-compose ps redis`
- [ ] Check Redis logs: `docker-compose logs redis`
- [ ] Restart Redis: `docker-compose restart redis`
- [ ] Verify REDIS_URL in .env is correct

### Issue: Health check shows degraded
- [ ] Check component status: `curl http://localhost:8001/health | jq .components`
- [ ] PostgreSQL unhealthy → Restart postgres: `docker-compose restart postgres`
- [ ] Redis unhealthy → Restart redis: `docker-compose restart redis`
- [ ] Celery unhealthy → Check if worker started yet (can take 30 seconds)
- [ ] OpenAI unhealthy → Not critical, LLM features disabled

### Issue: High memory usage
- [ ] Check container memory: `docker stats`
- [ ] Check database connections: `docker-compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"`
- [ ] Reduce pool size in backend/database.py if needed
- [ ] Restart containers: `docker-compose restart`

---

## Maintenance Tasks (After Deployment)

### Daily
- [ ] Check health endpoint: `curl http://localhost:8001/health`
- [ ] Review error logs: `docker-compose logs | grep ERROR`
- [ ] Verify Celery is processing tasks

### Weekly
- [ ] Review database disk usage
- [ ] Check performance metrics
- [ ] Review memory and CPU usage
- [ ] Update logs for analysis

### Monthly
- [ ] Full database backup
- [ ] Review and optimize slow queries
- [ ] Update dependencies: `pip install --upgrade -r requirements.txt`
- [ ] Test disaster recovery (restore from backup)

### Quarterly
- [ ] Security audit
- [ ] Performance optimization review
- [ ] Capacity planning review
- [ ] Documentation update

---

## Documentation Location

| Document | Purpose | Read When |
|----------|---------|-----------|
| PRODUCTION_SETUP.md | Complete setup guide | Before deployment |
| UPGRADE_SUMMARY.md | Technical details | For understanding changes |
| DEPLOYMENT_READY.md | Executive summary | For approval/review |
| CHANGES_INDEX.md | Detailed change log | For technical review |
| validate_production.sh | Automated tests | Before deployment |
| This file | Deployment checklist | During deployment |

---

## Success Criteria

Deployment is successful when:

✅ All services are healthy and running  
✅ Health endpoint returns `"status": "healthy"`  
✅ No ERROR or CRITICAL logs in first hour  
✅ Database tables are created  
✅ pgvector extension is installed  
✅ Celery workers are processing tasks  
✅ API responds with <100ms latency  
✅ No connection pool exhaustion  
✅ Backup is verified and accessible  
✅ All team members notified of successful deployment  

---

## Sign-Off

- [ ] Deployment Engineer: _______________  Date: _______
- [ ] QA Lead: _______________  Date: _______
- [ ] DevOps Lead: _______________  Date: _______
- [ ] Product Lead: _______________  Date: _______

---

## Post-Deployment Notes

```
Date Deployed: ________________
Deployed By: ________________
Version: 4.1.0
Duration: ________________ minutes
Issues Encountered: ________________
Resolution: ________________
Notes: ________________
```

---

**Last Updated**: December 2024  
**Version**: 1.0  
**Status**: Ready for Use
