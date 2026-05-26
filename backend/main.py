# backend/main.py
import os
import asyncio
import logging
import uvicorn
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

# 📦 Configure Structured JSON Logging immediately on application boot
from backend.config.logging_config import setup_production_logging
setup_production_logging()

from backend.config.settings import settings

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

logger = logging.getLogger(__name__)

# =========================
# 🔹 LOAD ENV
# =========================
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))

# =========================
# 🔹 IMPORT MODULES
# =========================
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from backend.database import engine, Base, get_db
from backend.webhook import router as webhook_router
from backend.user import router as auth_router
from backend.strava_auth import router as strava_auth_router
from backend.models import User, Activity
from backend.celery_app import celery_app
import redis
import httpx

# =========================
# 🔹 FASTAPI INIT
# =========================
app = FastAPI(
    title="Veda AI Endurance Coach",
    description="AI-powered endurance coaching system",
    version="4.0.0"
)

# =========================
# 🔹 CORS (Strict Production Lock)
# =========================
PRODUCTION_DOMAIN = os.getenv("ALLOWED_ORIGIN", "https://yourcoachingapp.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[PRODUCTION_DOMAIN],  # Explicitly locked domain. No wildcard "*" bypasses allowed.
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# =========================
# 🔹 TEMPLATES
# =========================
base_path = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(base_path / "templates"))

# =========================
# 🚀 STARTUP EVENT
# =========================
@app.on_event("startup")
async def startup_event():
    logger.info({"event": "app_startup_sequence_initialized"})

    # 1. Warm cache slightly (asynchronously)
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        logger.info({"event": "redis_dependency_validated", "status": "healthy"})
    except Exception as e:
        logger.critical({"event": "redis_dependency_failed", "error": str(e)})
        # Do not block startup; let health check capture and report failures
        
    logger.info({"event": "app_startup_completed", "message": "Ready to receive traffic. Startup sync deferred to Celery Beat."})


# =========================
# 🏠 BASIC ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# =========================
# 🩺 COMPREHENSIVE HEALTH CHECK
# =========================
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "postgres": "unhealthy",
        "redis": "unhealthy",
        "celery_workers_active": 0,
        "openai_connection": "unhealthy"
    }
    
    overall_healthy = True
    
    # 1. Verify PostgreSQL Connection
    try:
        start_time = time.time()
        db.execute(text("SELECT 1"))
        health_status["postgres"] = f"healthy (latency: {round((time.time() - start_time) * 1000, 1)}ms)"
    except Exception as e:
        health_status["postgres"] = f"unhealthy ({str(e)})"
        overall_healthy = False
        
    # 2. Verify Redis Connection
    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        start_time = time.time()
        r.ping()
        health_status["redis"] = f"healthy (latency: {round((time.time() - start_time) * 1000, 1)}ms)"
    except Exception as e:
        health_status["redis"] = f"unhealthy ({str(e)})"
        overall_healthy = False

    # 3. Check Active Celery Workers
    try:
        inspect = celery_app.control.inspect(timeout=1.0)
        active = inspect.active()
        if active:
            health_status["celery_workers_active"] = len(active)
    except Exception:
        health_status["celery_workers_active"] = "error reading control structures"

    # 4. Verify OpenAI Connection
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"})
            if resp.status_code == 200:
                health_status["openai_connection"] = "healthy"
            else:
                health_status["openai_connection"] = f"unhealthy (HTTP {resp.status_code})"
                overall_healthy = False
    except Exception as e:
        health_status["openai_connection"] = f"failed to reach API ({str(e)})"
        overall_healthy = False

    if not overall_healthy:
        health_status["status"] = "degraded"
        
    return health_status

# =========================
# 📊 DASHBOARD API
# =========================
@app.get("/api/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Returns aggregate stats for the primary user (mocking for single-user pilot)"""
    # For now, we fetch stats for the first active user
    user = db.query(User).filter_by(is_active=True).first()
    if not user:
        return {"total_distance": 0, "total_runs": 0, "avg_pace": "0:00"}
    
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

@app.get("/api/activities")
def get_activities(db: Session = Depends(get_db)):
    """Returns recent activities for the dashboard"""
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

# =========================
# 🔹 ROUTERS
# =========================
from backend.strava_webhooks import router as strava_webhook_router

app.include_router(webhook_router)        # Handles Telegram: /webhook/telegram
app.include_router(auth_router)           # Handles Local Auth: /auth/register
app.include_router(strava_auth_router)    # Handles Strava Auth: /auth/callback
app.include_router(strava_webhook_router) # Handles Strava Webhooks: /webhook/strava

# =========================
# ▶️ ENTRY POINT
# =========================
if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)
