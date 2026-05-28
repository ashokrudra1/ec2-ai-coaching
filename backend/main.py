# backend/main.py
"""
Veda AI Endurance Coach - Production FastAPI Application
Handles API requests, real-time coaching, and system orchestration.
"""
import os
import asyncio
import logging
import sys
import uvicorn
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

# ============================================================================
# 1. EARLY LOGGING SETUP (Before any other imports)
# ============================================================================
from backend.config.logging_config import setup_production_logging
# Force UTF-8 process I/O for Windows and mixed shell environments.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
setup_production_logging()
logger = logging.getLogger(__name__)

# ============================================================================
# 2. LOAD ENVIRONMENT VARIABLES
# ============================================================================
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))

from backend.config.settings import settings

# ============================================================================
# 3. CONFIGURE SENTRY (BEFORE ANY APP INITIALIZATION)
# ============================================================================
if settings.SENTRY_DSN:
    logger.info("🔴 Initializing Sentry error tracking...")
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
else:
    logger.warning("⚠️ SENTRY_DSN not configured. Error tracking disabled.")

# ============================================================================
# 4. IMPORT CORE MODULES
# ============================================================================
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from backend.database import (
    engine,
    Base,
    get_db,
    initialize_database,
    health_check
)
from backend.webhook import router as webhook_router
from backend.user import router as auth_router
from backend.strava_auth import router as strava_auth_router
from backend.models import User, Activity
from backend.celery_app import celery_app
from backend.observability.metrics import snapshot_metrics
from backend.security.usage_governance import UsageGovernor
import redis
import httpx

# ============================================================================
# 5. LIFESPAN CONTEXT (App startup/shutdown)
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler for startup and shutdown events.
    
    Startup:
    - Initialize database (migrations, pgvector, tables)
    - Validate environment variables
    - Warm Redis cache
    
    Shutdown:
    - Gracefully close connections
    """
    logger.info("=" * 80)
    logger.info("🚀 VEDA AI COACHING SYSTEM - STARTUP SEQUENCE INITIATED")
    logger.info("=" * 80)
    
    try:
        # ====================================================================
        # PHASE 1: DATABASE INITIALIZATION (Critical path)
        # ====================================================================
        logger.info("📍 PHASE 1: Database Initialization")
        try:
            initialize_database()
        except Exception as e:
            logger.critical(f"❌ Database initialization failed: {str(e)}")
            logger.critical("🛑 Cannot proceed without database. Aborting startup.")
            raise
        
        # ====================================================================
        # PHASE 2: ENVIRONMENT VALIDATION
        # ====================================================================
        logger.info("📍 PHASE 2: Environment Validation")
        required_env_vars = [
            "OPENAI_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "REDIS_URL"
        ]
        
        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                logger.warning(f"⚠️  Missing environment variable: {var}")
        
        if missing_vars:
            logger.warning(
                f"⚠️  Application will run but some features may be unavailable. "
                f"Missing: {', '.join(missing_vars)}"
            )
        else:
            logger.info("✅ All required environment variables configured")
        
        # ====================================================================
        # PHASE 3: REDIS HEALTH CHECK & WARM CACHE
        # ====================================================================
        logger.info("📍 PHASE 3: Redis Connection & Cache Warm-up")
        try:
            r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=5)
            r.ping()
            logger.info("✅ Redis connection validated")
            
            # Warm cache with a simple operation
            r.set("app_startup_timestamp", datetime.now(timezone.utc).isoformat(), ex=86400)
            logger.info("✅ Redis cache warmed")
        except Exception as e:
            logger.warning(f"⚠️  Redis connection failed: {str(e)}")
            logger.warning("🔴 Celery tasks will not work without Redis!")
        
        # ====================================================================
        # PHASE 4: CELERY HEALTH CHECK
        # ====================================================================
        logger.info("📍 PHASE 4: Celery Worker Availability Check")
        try:
            inspect = celery_app.control.inspect(timeout=2.0)
            if inspect.ping():
                logger.info("✅ Celery workers are available")
            else:
                logger.warning("⚠️  No Celery workers detected (expected if workers not started)")
        except Exception as e:
            logger.warning(f"⚠️  Could not inspect Celery workers: {str(e)}")
        
        # ====================================================================
        # PHASE 5: OPENAI CONNECTIVITY TEST
        # ====================================================================
        logger.info("📍 PHASE 5: OpenAI API Connectivity Test")
        if os.getenv("OPENAI_API_KEY"):
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')[:10]}..."}
                    )
                    if resp.status_code == 200:
                        logger.info("✅ OpenAI API is reachable")
                    else:
                        logger.warning(f"⚠️  OpenAI API returned status {resp.status_code}")
            except Exception as e:
                logger.warning(f"⚠️  OpenAI connectivity check failed: {str(e)}")
        else:
            logger.warning("⚠️  OPENAI_API_KEY not configured. LLM features disabled.")
        
        # ====================================================================
        # STARTUP COMPLETE
        # ====================================================================
        logger.info("=" * 80)
        logger.info("✅ STARTUP SEQUENCE COMPLETED SUCCESSFULLY")
        logger.info("🟢 Application ready to receive traffic")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.critical(f"❌ Startup sequence failed with error: {str(e)}")
        raise
    
    # Yield control to the application
    yield
    
    # ========================================================================
    # SHUTDOWN PHASE
    # ========================================================================
    logger.info("=" * 80)
    logger.info("🛑 SHUTDOWN SEQUENCE INITIATED")
    logger.info("=" * 80)
    
    try:
        # Close database connections
        engine.dispose()
        logger.info("✅ Database connections closed")
        
        # Revoke any pending Celery tasks
        try:
            celery_app.control.purge()
            logger.info("✅ Celery task queue purged")
        except Exception as e:
            logger.warning(f"⚠️  Could not purge Celery queue: {str(e)}")
        
        logger.info("=" * 80)
        logger.info("✅ SHUTDOWN SEQUENCE COMPLETED")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Shutdown error: {str(e)}")

# ============================================================================
# 6. CREATE FASTAPI APPLICATION
# ============================================================================
app = FastAPI(
    title="Veda AI Endurance Coach",
    description="AI-powered endurance coaching system with real-time training analysis",
    version="4.1.0",
    lifespan=lifespan  # Register lifespan handler
)

# ============================================================================
# 7. MIDDLEWARE CONFIGURATION
# ============================================================================
# CORS Configuration (Strict Production Lock)
ALLOWED_ORIGINS = [
    os.getenv("ALLOWED_ORIGIN", "https://vedaactivewellness.xyz"),
    "http://localhost:3000",      # Development frontend
    "http://localhost:8001",      # Development API
]

if os.getenv("ENVIRONMENT", "production").lower() == "development":
    logger.warning("🔓 DEVELOPMENT MODE: Relaxed CORS configuration")
    ALLOWED_ORIGINS.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Add Sentry middleware
if settings.SENTRY_DSN:
    app.add_middleware(SentryAsgiMiddleware)

# ============================================================================
# 8. TEMPLATE CONFIGURATION
# ============================================================================
base_path = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_path / "templates"))

# ============================================================================
# 9. BASIC ROUTES
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render homepage"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/ping")
async def ping():
    """Simple ping endpoint for load balancer health checks"""
    return {"status": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}

# ============================================================================
# 10. COMPREHENSIVE HEALTH CHECK ENDPOINT
# ============================================================================
@app.get("/health")
def health_check_endpoint(db: Session = Depends(get_db)):
    """
    Comprehensive health check providing detailed system status.
    
    Returns JSON with status of:
    - PostgreSQL connection & latency
    - Redis connection & latency
    - Active Celery workers
    - OpenAI API connectivity
    - Database migration status
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "4.1.0",
        "components": {
            "postgres": {"status": "unhealthy", "latency_ms": None},
            "redis": {"status": "unhealthy", "latency_ms": None},
            "celery_workers": {"status": "unhealthy", "count": 0},
            "openai": {"status": "unhealthy"},
            "database_tables": {"status": "unhealthy"}
        }
    }
    
    overall_healthy = True
    
    # ====================================================================
    # 1. PostgreSQL Health Check
    # ====================================================================
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        latency_ms = round((time.time() - start_time) * 1000, 2)
        health_status["components"]["postgres"] = {
            "status": "healthy",
            "latency_ms": latency_ms
        }
    except Exception as e:
        health_status["components"]["postgres"]["status"] = f"unhealthy: {str(e)[:50]}"
        overall_healthy = False
    
    # ====================================================================
    # 2. Database Migration Status
    # ====================================================================
    try:
        # Check if critical tables exist
        result = db.execute(text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'users'"
        )).scalar()
        
        if result and result > 0:
            health_status["components"]["database_tables"]["status"] = "healthy"
        else:
            health_status["components"]["database_tables"]["status"] = "unhealthy: users table missing"
            overall_healthy = False
    except Exception as e:
        health_status["components"]["database_tables"]["status"] = f"error: {str(e)[:50]}"
        overall_healthy = False
    
    # ====================================================================
    # 3. Redis Health Check
    # ====================================================================
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=3)
        start_time = time.time()
        r.ping()
        latency_ms = round((time.time() - start_time) * 1000, 2)
        health_status["components"]["redis"]["status"] = "healthy"
        health_status["components"]["redis"]["latency_ms"] = latency_ms
    except Exception as e:
        health_status["components"]["redis"]["status"] = f"unhealthy: {str(e)[:50]}"
        overall_healthy = False
    
    # ====================================================================
    # 4. Celery Workers Health Check
    # ====================================================================
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        active = inspect.active()
        if active:
            worker_count = len(active)
            health_status["components"]["celery_workers"] = {
                "status": "healthy",
                "count": worker_count
            }
        else:
            health_status["components"]["celery_workers"]["status"] = "no workers active"
            # Not marking overall as unhealthy since workers may not be started yet
    except Exception as e:
        health_status["components"]["celery_workers"]["status"] = f"error: {str(e)[:50]}"
    
    # ====================================================================
    # 5. OpenAI API Health Check
    # ====================================================================
    if os.getenv("OPENAI_API_KEY"):
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')[:10]}..."}
                )
                if resp.status_code == 200:
                    health_status["components"]["openai"]["status"] = "healthy"
                else:
                    health_status["components"]["openai"]["status"] = f"unhealthy: HTTP {resp.status_code}"
                    overall_healthy = False
        except Exception as e:
            health_status["components"]["openai"]["status"] = f"unreachable: {str(e)[:50]}"
            overall_healthy = False
    else:
        health_status["components"]["openai"]["status"] = "skipped: OPENAI_API_KEY not configured"
    
    # ====================================================================
    # Set overall status
    # ====================================================================
    if not overall_healthy:
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/health/metrics")
def health_metrics_snapshot():
    """In-process metrics snapshot for quick operational debugging."""
    return snapshot_metrics()


@app.get("/ops/org-cost/{org_id}")
def org_cost_summary(org_id: str, db: Session = Depends(get_db)):
    """Tenant-level spend and token visibility for SaaS operations."""
    return UsageGovernor.get_org_cost_summary(db, org_id)

# ============================================================================
# 11. DASHBOARD STATISTICS ENDPOINTS
# ============================================================================
@app.get("/api/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Returns aggregate stats for the primary active user"""
    try:
        user = db.query(User).filter_by(is_active=True).first()
        if not user:
            return {
                "total_distance": 0,
                "total_runs": 0,
                "avg_pace": "0:00",
                "error": "No active user found"
            }
        
        total_distance = db.query(func.sum(Activity.distance_km)).filter_by(user_id=user.id).scalar() or 0
        total_runs = db.query(func.count(Activity.id)).filter_by(user_id=user.id).scalar() or 0
        
        # Calculate average pace (min/km)
        total_moving_time = db.query(func.sum(Activity.moving_time_min)).filter_by(user_id=user.id).scalar() or 0
        if total_distance > 0:
            avg_pace_raw = total_moving_time / total_distance
            minutes = int(avg_pace_raw)
            seconds = int((avg_pace_raw - minutes) * 60)
            avg_pace = f"{minutes}:{seconds:02d}"
        else:
            avg_pace = "0:00"

        return {
            "total_distance": round(total_distance, 1),
            "total_runs": total_runs,
            "avg_pace": avg_pace
        }
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        return {"error": str(e), "status": "error"}


@app.get("/api/activities")
def get_activities(db: Session = Depends(get_db)):
    """Returns recent activities for the dashboard"""
    try:
        user = db.query(User).filter_by(is_active=True).first()
        if not user:
            return []
        
        activities = (
            db.query(Activity)
            .filter_by(user_id=user.id)
            .order_by(Activity.start_date_utc.desc())
            .limit(10)
            .all()
        )
        
        return [
            {
                "id": a.id,
                "name": a.name,
                "distance": round(a.distance_km, 2),
                "date": a.start_date_utc.strftime("%Y-%m-%d"),
                "type": a.type
            }
            for a in activities
        ]
    except Exception as e:
        logger.error(f"Error fetching activities: {str(e)}")
        return []

# ============================================================================
# 12. INCLUDE ROUTERS
# ============================================================================
from backend.strava_webhooks import router as strava_webhook_router
from backend.decision_traces import router as decision_trace_router
from backend.live_coaching.routes import router as live_coaching_router

app.include_router(webhook_router)           # Telegram webhooks
app.include_router(auth_router)              # Local auth
app.include_router(strava_auth_router)       # Strava OAuth
app.include_router(strava_webhook_router)    # Strava activity webhooks
app.include_router(decision_trace_router)    # Coaching explainability traces
app.include_router(live_coaching_router)     # Real-time intervention evaluation

# ============================================================================
# 13. ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=False)
