# backend/athlete_state/physiology_engine.py
from statistics import mean

class PhysiologyEngine:

    @staticmethod
    def calculate_hr_zones(user):
        max_hr = user.max_hr or 190
        rest_hr = user.rest_hr or 60
        reserve = max_hr - rest_hr

        return {
            "zone1": round(rest_hr + reserve * 0.60),
            "zone2": round(rest_hr + reserve * 0.70),
            "zone3": round(rest_hr + reserve * 0.80),
            "zone4": round(rest_hr + reserve * 0.90),
            "zone5": max_hr
        }

    @staticmethod
    def calculate_efficiency(activity):
        if not activity.avg_heart_rate or not activity.distance_km:
            return None
        # Efficiency = Distance / Avg Heart Rate (Higher index indicates higher fitness efficiency)
        return round(activity.distance_km / activity.avg_heart_rate, 3)
