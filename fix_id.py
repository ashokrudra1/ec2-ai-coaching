from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Manually setting your Strava ID (which we saw was 70799315 earlier)
    conn.execute(text("UPDATE users SET strava_athlete_id = '70799315' WHERE id = 5;"))
    # Clear tokens to force a fresh, clean write
    conn.execute(text("DELETE FROM strava_tokens WHERE user_id = 5;"))
    conn.commit()
    print("✅ Profile 5 manually linked to Strava ID 70799315.")
