# backend/environmental/weather_intelligence.py
import logging

logger = logging.getLogger(__name__)

class WeatherIntelligence:
    """
    Environmental Stress Analysis Engine.
    Adjusts pacing and recovery metrics based on weather, AQI, and altitude.
    """

    @staticmethod
    def calculate_effective_pacing_penalty(
        temp_c: float, 
        humidity: float, 
        elevation_m: float, 
        aqi: int = 50
    ) -> dict:
        """
        Calculates pace adjustments (seconds per kilometer) based on environmental stress.
        """
        try:
            pace_adjustment_sec = 0.0
            cardiac_load_penalty = 1.0

            # 1. Heat and Humidity Stress (Calculates dew point approximation)
            # A high dew point (> 18°C) impairs the body's ability to cool itself
            dew_point = temp_c - ((100.0 - humidity) / 5.0)
            if dew_point > 16.0:
                # Add 2 seconds per km for every degree above 16°C
                pace_adjustment_sec += (dew_point - 16.0) * 2.5
                cardiac_load_penalty += (dew_point - 16.0) * 0.02

            # 2. Altitude Adaptation Penalty (Reduces oxygen availability)
            if elevation_m > 1000.0:
                # Every 500m above 1000m altitude adds a 1.5% pacing penalty
                altitude_offset = (elevation_m - 1000.0) / 500.0
                pace_adjustment_sec += altitude_offset * 4.0
                cardiac_load_penalty += altitude_offset * 0.03

            # 3. Air Quality Index (AQI) Safety Boundary
            aqi_warning = False
            if aqi > 150:
                aqi_warning = True
                # Severe respiratory load penalty
                pace_adjustment_sec += (aqi - 150) * 0.2
                cardiac_load_penalty += (aqi - 150) * 0.005

            return {
                "pace_adjustment_sec_per_km": round(pace_adjustment_sec, 1),
                "cardiac_load_multiplier": round(cardiac_load_penalty, 3),
                "unsafe_air_quality_warning": aqi_warning,
                "dew_point_c": round(dew_point, 1)
            }

        except Exception as e:
            logger.error(f"❌ WeatherIntelligence execution failed: {str(e)}")
            return {"pace_adjustment_sec_per_km": 0.0, "cardiac_load_multiplier": 1.0, "unsafe_air_quality_warning": False, "dew_point_c": 15.0}
