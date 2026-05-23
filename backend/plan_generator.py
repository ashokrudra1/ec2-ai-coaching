# backend/plan_generator.py
from backend.models import User
from backend.analytics import get_fatigue_metrics
from backend.athlete_state.physiology_engine import PhysiologyEngine

def generate_training_plan(db, user_id, goal="general"):
    """
    Generates an adaptive, biometric-locked training plan
    based on real-time fatigue, goal, and the athlete's precise HR Zones.
    """
    atl, ctl, tsb, fatigue = get_fatigue_metrics(db, user_id)
    user = db.query(User).filter_by(id=user_id).first()
    
    # Calculate physiological thresholds dynamically
    zones = PhysiologyEngine.calculate_hr_zones(user) if user else {
        "zone1": 115, "zone2": 133, "zone3": 152, "zone4": 171, "zone5": 190
    }
    
    goal = (goal or "general").lower()

    # =========================
    # 🔴 OVERTRAINING CASE
    # =========================
    if fatigue == "Overtraining" or tsb < -20:
        plan = [
            "Complete Rest Day - Active recovery / stretching only.",
            "Light mobility / foam rolling.",
            f"Very easy recovery jog (Zone 1: Under {zones['zone1']} bpm) - max 20 mins."
        ]
        note = "Your system is showing high fatigue. Prioritize recovery to prevent injury."

    # =========================
    # 🟡 HIGH FATIGUE
    # =========================
    elif tsb < -5:
        plan = [
            f"Easy Recovery Run (Zone 1/2: {zones['zone1']}-{zones['zone2']} bpm) - max 30 mins.",
            "Light walk / low-impact active movement.",
            f"Zone 2 Endurance Session (Target: {zones['zone1']}-{zones['zone2']} bpm) - max 40 mins."
        ]
        note = "Ensure yesterday's training stress is absorbed. Keep intensity low."

    # =========================
    # 🟢 GOOD FORM (OPTIMAL TRAINING)
    # =========================
    elif -5 <= tsb <= 10:
        if "marathon" in goal:
            plan = [
                f"Long Aerobic Run (Zone 2 Baseline: {zones['zone1']}-{zones['zone2']} bpm) - Building aerobic volume.",
                f"Active Recovery Jog (Zone 1: Under {zones['zone1']} bpm) - 30 mins.",
                f"Tempo Block (10 min Warmup -> 20 mins in Zone 3: {zones['zone2']}-{zones['zone3']} bpm -> 10 min Cooldown)."
            ]
        elif "5k" in goal or "10k" in goal:
            plan = [
                f"Interval speed work (4 x 800m hitting Zone 4: {zones['zone3']}-{zones['zone4']} bpm, with full recovery jogs).",
                f"Easy Base Run (Zone 2: {zones['zone1']}-{zones['zone2']} bpm) - 45 mins.",
                f"Threshold Tempo (30 mins steady effort in Zone 3: {zones['zone2']}-{zones['zone3']} bpm)."
            ]
        else:
            plan = [
                f"Steady Base Run (Zone 2: {zones['zone1']}-{zones['zone2']} bpm) - 45 mins.",
                f"Active Recovery Jog (Zone 1: Under {zones['zone1']} bpm) - 30 mins.",
                f"Mixed Fartlek (Warmup -> 5x 1-min repeats in Zone 4: {zones['zone3']}-{zones['zone4']} bpm -> Cooldown)."
            ]
        note = "Your training stress balance is optimal. Proceed with targeted quality sessions."

    # =========================
    # 🔵 FRESH (LOW FATIGUE)
    # =========================
    else:
        plan = [
            f"Speed Intervals (6 x 400m reaching Zone 4/5: {zones['zone3']}-{zones['zone5']} bpm).",
            f"Endurance Run (Zone 2 Baseline: {zones['zone1']}-{zones['zone2']} bpm) - 60 mins.",
            f"Threshold Progression Run (Zone 2 running into Zone 3: {zones['zone1']}-{zones['zone3']} bpm)."
        ]
        note = "You are carrying very low fatigue. High capacity for quality cardiovascular stress."

    # =========================
    # 📤 FORMAT OUTPUT
    # =========================
    msg = f"📅 *Adaptive 3-Day Training Protocol*\n"
    msg += f"🎯 Target Goal: {goal.capitalize()}\n"
    msg += f"⚡ Fatigue Balance: {fatigue} (TSB: {round(tsb, 1)})\n\n"

    for i, day in enumerate(plan, 1):
        msg += f"*Day {i}:* {day}\n"

    msg += f"\n💡 *Coach Note:* {note}"
    return msg
