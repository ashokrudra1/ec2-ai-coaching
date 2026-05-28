# backend/orchestration/conflict_resolver.py
"""
Conflict Resolution Router - Sports-Science Safety Guards

Programmatic checks BEFORE LLM generation to prevent:
- Overtraining injuries (ACWR > 1.5, TSB < -20)
- Medical constraint violations
- Unsafe training recommendations

Author: Veda AI Elite Architecture Team
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models import User, Activity
from backend.orchestration.metrics_engine import TrainingMetricsEngine, WorkoutDataPoint, SafetyCheckResult

logger = logging.getLogger(__name__)


# ============================================================================
# SAFETY THRESHOLDS (Sports-Science Backed)
# ============================================================================

class SafetyThresholds:
    """Injury prevention thresholds based on training science research"""
    
    TSB_CRITICAL_LOW = -20.0  # Absolute recovery threshold
    TSB_MODERATE_LOW = -10.0  # Elevated fatigue warning
    
    ACWR_CRITICAL_HIGH = 1.5  # High injury risk zone
    ACWR_MODERATE_HIGH = 1.2  # Moderate injury risk zone
    ACWR_OPTIMAL_MIN = 0.8    # Minimum training stimulus
    
    # Medical restrictions
    MEDICAL_KEYWORDS_CRITICAL = [
        "stress fracture", "tendinitis", "cartilage damage", "bone", "fracture"
    ]
    
    MEDICAL_KEYWORDS_MODERATE = [
        "inflammation", "tendinopathy", "strain", "sprain", "overuse"
    ]


# ============================================================================
# CONFLICT RESOLUTION ROUTER
# ============================================================================

class ConflictResolutionRouter:
    """
    Programmatic safety layer that intercepts and overrides unsafe LLM recommendations.
    
    Called BEFORE LLM generation in CoachService.generate()
    
    Decision Tree:
    1. Check TSB level → If < -20, force recovery mode
    2. Check ACWR → If > 1.5, cap intensity to 70%
    3. Check medical insights → Apply restrictions
    4. Aggregate into override decision
    5. Inject safety alert into system prompt
    """
    
    @classmethod
    async def check_safety(
        cls,
        session: Session,
        user_id: int,
        requested_workout: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """
        Comprehensive safety check for a user's requested workout.
        
        Args:
            session: SQLAlchemy session
            user_id: Athlete ID
            requested_workout: Optional workout details to validate
            
        Returns:
            SafetyCheckResult with override decision and adjusted intensity
        """
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User {user_id} not found")
                return SafetyCheckResult(
                    override_active=False,
                    medical_restrictions=[]
                )
            
            logger.info(f"🛡️  Safety check initiated for user {user_id}")
            
            # Step 1: Recalculate metrics from recent activity history
            metrics = await cls._recalculate_user_metrics(session, user)
            
            # Step 2: Check TSB threshold
            tsb_check = cls._check_tsb(metrics.tsb)
            
            # Step 3: Check ACWR
            acwr_check = cls._check_acwr(metrics.acwr, metrics.ctl, metrics.atl)
            
            # Step 4: Check medical constraints
            medical_check = cls._check_medical_constraints(user)
            
            # Step 5: Aggregate all checks
            result = cls._aggregate_safety_checks(
                tsb_check=tsb_check,
                acwr_check=acwr_check,
                medical_check=medical_check,
                metrics=metrics
            )
            
            logger.info(
                f"✅ Safety check complete: Override={result.override_active}, "
                f"Intensity={result.suggested_intensity}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Safety check failed: {str(e)}", exc_info=True)
            # Fail open (safe): don't block, but log issue
            return SafetyCheckResult(
                override_active=False,
                medical_restrictions=[]
            )
    
    
    @classmethod
    async def _recalculate_user_metrics(
        cls,
        session: Session,
        user: User
    ) -> Any:
        """
        Fetch recent activity history and recalculate CTL/ATL/TSB metrics.
        
        Args:
            session: SQLAlchemy session
            user: User object
            
        Returns:
            TrainingMetrics object
        """
        try:
            # Get last 100 activities
            recent_activities = session.query(Activity).filter(
                Activity.user_id == user.id
            ).order_by(Activity.start_date_utc.desc()).limit(100).all()
            
            if not recent_activities:
                logger.warning(f"No activities found for user {user.id}")
                return TrainingMetricsEngine.calculate_metrics([])
            
            # Convert to WorkoutDataPoint
            workouts = [
                WorkoutDataPoint(
                    date=activity.start_date_utc,
                    tss=activity.training_stress_score_tss or 0.0,
                    duration_min=activity.moving_time_min,
                    distance_km=activity.distance_km,
                    avg_hr=activity.avg_heart_rate,
                    max_hr=activity.max_heart_rate,
                    avg_cadence=activity.avg_cadence
                )
                for activity in reversed(recent_activities)  # Reverse to chronological order
            ]
            
            # Calculate metrics
            metrics = TrainingMetricsEngine.calculate_metrics(
                workouts,
                current_ctl=user.ctl,
                current_atl=user.atl
            )
            
            logger.debug(f"Recalculated metrics for user {user.id}: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to recalculate metrics: {str(e)}")
            # Return user's current values
            return type('Metrics', (), {
                'ctl': user.ctl,
                'atl': user.atl,
                'tsb': user.tsb,
                'acwr': user.atl / user.ctl if user.ctl > 0 else 0.0
            })()
    
    
    @classmethod
    def _check_tsb(cls, tsb: float) -> Dict[str, Any]:
        """
        Check Training Stress Balance thresholds.
        
        Returns:
            Dict with override_required, warning_level, suggested_action
        """
        if tsb < SafetyThresholds.TSB_CRITICAL_LOW:
            return {
                "override_required": True,
                "warning_level": "critical",
                "reason": f"TSB critically low: {tsb:.1f}",
                "suggested_action": "force_recovery"
            }
        elif tsb < SafetyThresholds.TSB_MODERATE_LOW:
            return {
                "override_required": True,
                "warning_level": "high",
                "reason": f"TSB elevated fatigue: {tsb:.1f}",
                "suggested_action": "reduce_intensity"
            }
        else:
            return {
                "override_required": False,
                "warning_level": "none",
                "reason": None,
                "suggested_action": None
            }
    
    
    @classmethod
    def _check_acwr(cls, acwr: float, ctl: float, atl: float) -> Dict[str, Any]:
        """
        Check Acute-to-Chronic Workload Ratio.
        
        Returns:
            Dict with override status and intensity cap
        """
        if acwr > SafetyThresholds.ACWR_CRITICAL_HIGH:
            return {
                "override_required": True,
                "warning_level": "critical",
                "reason": f"ACWR spike: {acwr:.2f} (high injury risk)",
                "intensity_cap": 0.70,  # 70% max intensity
                "suggested_action": "cap_to_z2"
            }
        elif acwr >= SafetyThresholds.ACWR_MODERATE_HIGH:
            return {
                "override_required": True,
                "warning_level": "moderate",
                "reason": f"ACWR elevated: {acwr:.2f}",
                "intensity_cap": 0.85,  # 85% max intensity
                "suggested_action": "reduce_intensity"
            }
        elif acwr < SafetyThresholds.ACWR_OPTIMAL_MIN:
            return {
                "override_required": False,
                "warning_level": "low",
                "reason": f"ACWR low (detraining risk): {acwr:.2f}",
                "intensity_cap": 1.0,
                "suggested_action": "increase_volume"
            }
        else:
            return {
                "override_required": False,
                "warning_level": "none",
                "reason": None,
                "intensity_cap": 1.0,
                "suggested_action": None
            }
    
    
    @classmethod
    def _check_medical_constraints(cls, user: User) -> Dict[str, Any]:
        """
        Check for medical restrictions in user.medical_insights.
        
        Returns:
            Dict with restrictions list and adjusted intensity
        """
        restrictions = []
        intensity_cap = 1.0
        
        if not user.medical_insights:
            return {
                "override_required": False,
                "restrictions": [],
                "intensity_cap": 1.0
            }
        
        medical_text = user.medical_insights.lower()
        
        # Check for critical restrictions
        for keyword in SafetyThresholds.MEDICAL_KEYWORDS_CRITICAL:
            if keyword in medical_text:
                restrictions.append(f"CRITICAL: {keyword} detected")
                intensity_cap = min(intensity_cap, 0.50)  # 50% max
        
        # Check for moderate restrictions
        for keyword in SafetyThresholds.MEDICAL_KEYWORDS_MODERATE:
            if keyword in medical_text:
                restrictions.append(f"MODERATE: {keyword} detected")
                intensity_cap = min(intensity_cap, 0.75)  # 75% max
        
        return {
            "override_required": len(restrictions) > 0,
            "restrictions": restrictions,
            "intensity_cap": intensity_cap
        }
    
    
    @classmethod
    def _aggregate_safety_checks(
        cls,
        tsb_check: Dict[str, Any],
        acwr_check: Dict[str, Any],
        medical_check: Dict[str, Any],
        metrics: Any
    ) -> SafetyCheckResult:
        """
        Aggregate all safety checks and determine final override decision.
        
        Returns:
            SafetyCheckResult with final recommendation
        """
        # Determine if override is required
        override_active = (
            tsb_check.get("override_required", False) or
            acwr_check.get("override_required", False) or
            medical_check.get("override_required", False)
        )
        
        # Calculate minimum intensity cap
        intensity_cap = min(
            acwr_check.get("intensity_cap", 1.0),
            medical_check.get("intensity_cap", 1.0)
        )
        
        # Determine suggested intensity
        if override_active:
            if tsb_check.get("warning_level") == "critical":
                suggested_intensity = "rest"
            elif tsb_check.get("warning_level") == "high" or intensity_cap <= 0.70:
                suggested_intensity = "active_recovery"
            elif intensity_cap <= 0.85:
                suggested_intensity = "z2_aerobic"
            else:
                suggested_intensity = "normal"
        else:
            suggested_intensity = "normal"
        
        # Build reason string
        reasons = []
        if tsb_check.get("reason"):
            reasons.append(tsb_check["reason"])
        if acwr_check.get("reason"):
            reasons.append(acwr_check["reason"])
        if medical_check.get("restrictions"):
            reasons.extend(medical_check["restrictions"])
        
        reason = " | ".join(reasons) if reasons else None
        
        return SafetyCheckResult(
            override_active=override_active,
            reason=reason,
            suggested_intensity=suggested_intensity,
            medical_restrictions=medical_check.get("restrictions", []),
            tsb_warning=tsb_check.get("reason"),
            acwr_warning=acwr_check.get("reason")
        )


# ============================================================================
# SYSTEM PROMPT INJECTION FOR LLM
# ============================================================================

def inject_safety_prefix(safety_check: SafetyCheckResult) -> str:
    """
    Generate a safety prefix to inject into LLM system prompt.
    
    Args:
        safety_check: SafetyCheckResult from ConflictResolutionRouter
        
    Returns:
        Safety alert string to prepend to coach persona prompt
    """
    if not safety_check.override_active:
        return ""
    
    prefix_lines = [
        "⚠️  SAFETY MODE ACTIVATED - Recovery Priority",
        ""
    ]
    
    if safety_check.tsb_warning:
        prefix_lines.append(f"TSB Status: {safety_check.tsb_warning}")
    
    if safety_check.acwr_warning:
        prefix_lines.append(f"Workload Status: {safety_check.acwr_warning}")
    
    if safety_check.medical_restrictions:
        prefix_lines.append("Medical Constraints:")
        for restriction in safety_check.medical_restrictions:
            prefix_lines.append(f"  • {restriction}")
    
    prefix_lines.extend([
        "",
        f"Prescribed Intensity: {safety_check.suggested_intensity.upper().replace('_', ' ')}",
        "Priority: Recovery and injury prevention over performance gains.",
        ""
    ])
    
    return "\n".join(prefix_lines)
