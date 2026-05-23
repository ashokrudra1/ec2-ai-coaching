from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 1. Clear the Strava Athlete ID for Ashok
    conn.execute(text("UPDATE users SET strava_athlete_id = NULL WHERE name LIKE '%Ashok%';"))
    # 2. Clear the token table again to ensure no stale data exists
    conn.execute(text("DELETE FROM strava_tokens;"))
    conn.commit()
    print("✅ Profile unlinked. Telegram will now show the Connect button.")
