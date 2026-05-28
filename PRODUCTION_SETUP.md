# 🏃 Veda AI Coaching - Production Deployment Guide

## Overview

This document covers the updated production-ready Veda AI Coaching backend system. All critical issues have been resolved:

- ✅ **pgvector Support**: PostgreSQL with pgvector extension for vector embeddings
- ✅ **Auto-Migrations**: Database tables created automatically on startup
- ✅ **Celery Ready**: Proper error handling and database initialization for background tasks
- ✅ **Health Checks**: Comprehensive health endpoints for monitoring
- ✅ **Production Hardened**: Multi-stage Docker builds, non-root users, proper logging

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 16+ with pgvector extension (automatically handled by docker-compose)
- Redis 7+ (automatically handled by docker-compose)

### 1. Setup Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual credentials
nano .env
```

**Required environment variables:**
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `OPENAI_API_KEY`: OpenAI API key
- `TELEGRAM_BOT_TOKEN`: Telegram bot token
- `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`: Strava OAuth credentials

### 2. Start the System

```bash
# Start all services (PostgreSQL, Redis, API, Celery)
docker-compose up -d

# Check logs
docker-compose logs -f api

# Verify health
curl http://localhost:8001/health
```

### 3. Verify Services Are Running

```bash
# API should be at http://localhost:8001
# PostgreSQL should be at localhost:5432
# Redis should be at localhost:6379

# Check API health
curl http://localhost:8001/health | jq

# Check database migrations completed
curl http://localhost:8001/api/stats
```

## Architecture Changes

### Database Initialization (Automatic)

When the API container starts:

1. **Wait for PostgreSQL** - Retries until database is available
2. **Ensure pgvector** - Creates pgvector extension if needed
3. **Run Migrations** - Executes Alembic migrations or falls back to `create_all()`
4. **Verify Tables** - Confirms all required tables exist

This eliminates manual migration steps and prevents Celery from failing due to missing tables.

### pgvector Setup

The docker-compose.yml now uses `pgvector/pgvector:pg16-latest` which includes:
- PostgreSQL 16
- pgvector extension pre-installed
- Initialization SQL that enables pgvector on startup

```yaml
postgres:
  image: pgvector/pgvector:pg16-latest
  volumes:
    - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/01-init-pgvector.sql
```

### Health Check Improvements

The new `/health` endpoint returns detailed component status:

```json
{
  "status": "healthy",
  "timestamp": "2024-12-23T10:30:00+00:00",
  "components": {
    "postgres": {
      "status": "healthy",
      "latency_ms": 2.5
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1.2
    },
    "celery_workers": {
      "status": "healthy",
      "count": 2
    },
    "database_tables": {
      "status": "healthy"
    },
    "openai": {
      "status": "healthy"
    }
  }
}
```

## Key Files Modified

### 1. `docker-compose.yml`
- **Updated PostgreSQL image** to `pgvector/pgvector:pg16-latest`
- **Added init SQL script** for pgvector extension
- **Improved health checks** with actual service testing
- **Added Redis persistence** with volumes
- **Proper service dependencies** with health conditions

### 2. `backend/main.py`
- **Lifespan context manager** replaces `@app.on_event("startup")`
- **Comprehensive startup sequence** with 5 phases:
  1. Database initialization
  2. Environment validation
  3. Redis health check
  4. Celery worker verification
  5. OpenAI connectivity test
- **Enhanced health check endpoint** with component status
- **Better error handling** with structured logging

### 3. `backend/database.py`
- **`initialize_database()`** - Main initialization function
- **`wait_for_database()`** - Retry logic for database availability
- **`ensure_pgvector_extension()`** - Create pgvector if needed
- **`run_alembic_migrations()`** - Run migrations with fallback to create_all()
- **`create_all_tables()`** - SQLAlchemy table creation
- **Logging** at each step for debugging

### 4. `backend/Dockerfile`
- **Multi-stage build** - Smaller final image
- **Non-root user** (`appuser`) for security
- **Health check** using `/health` endpoint
- **Proper Python environment variables**

### 5. `backend/celery_app.py`
- **Better error handling** with retry logic
- **Task routing** to prevent queue starvation
- **Signal handlers** for task lifecycle logging
- **Production-grade configuration**

### 6. `requirements.txt`
- Added `gunicorn` for production WSGI server
- Added `structlog` for structured logging

### 7. `scripts/init_database.py`
- Utility script for manual database operations
- Check current state
- Perform full reset if needed

### 8. `scripts/init_db.sql`
- SQL script that runs on PostgreSQL startup
- Creates pgvector extension
- Configures database for production

## Running Locally (Development)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://postgres:[REDACTED]@localhost:5432/postgres
export REDIS_URL=redis://localhost:6379/0

# Start PostgreSQL and Redis with Docker
docker-compose up postgres redis -d

# Initialize database
python scripts/init_database.py

# Start FastAPI server
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001

# In another terminal, start Celery worker
celery -A backend.celery_app worker -Q chat_critical,data_sync,onboarding_heavy,scheduled_reports,celery --loglevel=info

# In another terminal, start Celery Beat
celery -A backend.celery_app beat --loglevel=info
```

## Deployment Checklist

- [ ] Copy `.env.example` to `.env` and fill in all required variables
- [ ] Verify PostgreSQL connection string is correct
- [ ] Verify Redis connection string is correct
- [ ] Ensure OPENAI_API_KEY is set
- [ ] Ensure TELEGRAM_BOT_TOKEN is set
- [ ] Ensure Strava OAuth credentials are set
- [ ] Run `docker-compose up -d`
- [ ] Wait 30-40 seconds for services to stabilize
- [ ] Verify with `curl http://localhost:8001/health`
- [ ] Check API logs: `docker-compose logs api`
- [ ] Check database migrations ran: `docker-compose logs postgres`
- [ ] Verify Celery is running: `docker-compose logs celery_worker`

## Monitoring & Debugging

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery_worker
docker-compose logs -f postgres

# Last N lines
docker-compose logs --tail=100 api
```

### Health Endpoints

```bash
# Overall health
curl http://localhost:8001/health | jq

# Dashboard stats
curl http://localhost:8001/api/stats | jq

# Ping endpoint (lightweight)
curl http://localhost:8001/ping | jq
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres

# Check tables
\dt

# Check pgvector
SELECT * FROM pg_extension WHERE extname = 'pgvector';

# Check recent Celery tasks
SELECT * FROM activities ORDER BY created_at DESC LIMIT 5;
```

### Celery Inspection

```bash
# Check active workers
celery -A backend.celery_app inspect active

# Check registered tasks
celery -A backend.celery_app inspect registered

# Purge pending tasks
celery -A backend.celery_app purge

# Monitor in real-time
celery -A backend.celery_app events
```

## Troubleshooting

### Issue: "pgvector extension not found"

**Solution**: The postgres image must be `pgvector/pgvector:pg16-latest`. Check `docker-compose.yml`:

```yaml
postgres:
  image: pgvector/pgvector:pg16-latest  # Correct
```

### Issue: "database tables missing" on Celery startup

**Solution**: Tables are created automatically when the API starts. Wait for:
```
✅ DATABASE INITIALIZATION COMPLETED SUCCESSFULLY
```

in the logs. Then start Celery.

### Issue: "Connection pool saturated"

**Solution**: Increase `max_overflow` and `pool_size` in `backend/database.py`:

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=40,       # Increase from 20
    max_overflow=80,    # Increase from 40
)
```

### Issue: "Redis connection refused"

**Solution**: Ensure Redis is running:

```bash
docker-compose ps redis
docker-compose logs redis
```

If Redis isn't running:
```bash
docker-compose up -d redis
```

### Issue: "Celery tasks failing with 'table does not exist'"

**Solution**: Wait for API to fully initialize before starting Celery. Check:

```bash
docker-compose logs api | grep "DATABASE INITIALIZATION COMPLETED"
```

## Production Recommendations

### 1. Database Backups
```bash
# Automated daily backups
docker-compose exec postgres pg_dump -U postgres > backup_$(date +%Y%m%d).sql
```

### 2. Monitor Disk Usage
```bash
docker-compose exec postgres df -h /var/lib/postgresql/data
```

### 3. Set Resource Limits
Update `docker-compose.yml`:
```yaml
api:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
```

### 4. Use Production Logging
Set `LOG_LEVEL=warning` in `.env` for production.

### 5. Regular Health Checks
```bash
# Automated monitoring
watch -n 30 'curl -s http://localhost:8001/health | jq .status'
```

## Support

For issues or questions:
1. Check the logs: `docker-compose logs -f`
2. Review this troubleshooting guide
3. Verify all environment variables are set
4. Ensure database is accessible
5. Confirm Redis is running

---

**Last Updated**: December 2024
**Version**: 4.1.0
**Changelog**:
- ✅ Added pgvector support with proper initialization
- ✅ Auto-migrations on application startup
- ✅ Comprehensive health checks with component status
- ✅ Production-hardened Docker images
- ✅ Improved error handling and logging
- ✅ Celery task routing to prevent queue starvation
- ✅ Database connection pooling optimization
