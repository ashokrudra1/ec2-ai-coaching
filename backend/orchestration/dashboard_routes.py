"""
Phase 8: Frontend Dashboard
Web UI for analytics, trends, and athlete data
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

from backend.database import get_db
from backend.models import User, Activity, PerformanceMetric, CoachMemory, PersonalRecord
from backend.training_system.coach_memory_engine import ContextAssembler

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/home")
async def get_home_dashboard(db: Session = Depends(get_db)):
    """
    Home dashboard: Quick overview of today's status and week summary
    """
    try:
        return {
            "status": "success",
            "endpoint": "Home Dashboard",
            "available_fields": ["today_activity", "current_state", "weekly_summary", "recommendations"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_analytics(days: int = 30, db: Session = Depends(get_db)):
    """
    Analytics dashboard: Historical trends, performance charts
    """
    try:
        return {
            "status": "success",
            "endpoint": "Analytics Dashboard",
            "period_days": days,
            "available_fields": ["activities", "metrics", "statistics", "trends"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance-records")
async def get_performance_records(db: Session = Depends(get_db)):
    """
    Personal records and achievements
    """
    try:
        return {
            "status": "success",
            "endpoint": "Personal Records",
            "available_fields": ["personal_records", "total_records"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-history")
async def get_chat_history(limit: int = 20, db: Session = Depends(get_db)):
    """
    Coaching chat history
    """
    try:
        return {
            "status": "success",
            "endpoint": "Chat History",
            "limit": limit,
            "available_fields": ["messages", "total_messages"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export-data")
async def export_data(db: Session = Depends(get_db)):
    """
    Export user data as JSON/CSV
    """
    try:
        return {
            "status": "success",
            "endpoint": "Data Export",
            "available_formats": ["json", "csv"],
            "includes": ["activities", "metrics", "messages", "learnings"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DashboardService:
    """
    Helper methods for dashboard data processing
    """

    @staticmethod
    def get_recommendations(state: Dict) -> List[str]:
        """Get coaching recommendations based on current state"""
        recommendations = []

        readiness = state.get("readiness", 0)
        injury_risk = state.get("injury_risk", 0)
        tsb = state.get("tsb", 0)

        if readiness > 85:
            recommendations.append("💪 You're in peak form! Go for a hard workout today.")
        elif readiness > 60:
            recommendations.append("🏃 Good readiness. Try a tempo session.")
        else:
            recommendations.append("😴 Focus on recovery today—easy pace only.")

        if injury_risk > 70:
            recommendations.append("⚠️ Injury risk is high. Take extra care with intensity.")

        if tsb < -30:
            recommendations.append("🛑 You're heavily fatigued. Consider a rest day.")

        return recommendations

    @staticmethod
    def format_activities_for_chart(activities: List) -> Dict:
        """Format activities for charting"""
        daily_data = {}

        for activity in activities:
            date = activity.start_date_utc.date()
            if date not in daily_data:
                daily_data[date] = {"volume_km": 0, "tss": 0, "workouts": 0}

            daily_data[date]["volume_km"] += activity.distance
            daily_data[date]["tss"] += activity.training_stress_score_tss or 0
            daily_data[date]["workouts"] += 1

        return {
            "daily": [
                {"date": str(date), **data}
                for date, data in sorted(daily_data.items())
            ]
        }

    @staticmethod
    def calculate_statistics(activities: List) -> Dict:
        """Calculate summary statistics"""
        if not activities:
            return {}

        return {
            "total_volume_km": sum(a.distance for a in activities),
            "total_tss": sum(a.training_stress_score_tss or 0 for a in activities),
            "total_workouts": len(activities),
            "avg_distance": sum(a.distance for a in activities) / len(activities),
            "max_distance": max(a.distance for a in activities) if activities else 0
        }
