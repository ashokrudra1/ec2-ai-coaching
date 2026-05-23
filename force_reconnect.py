from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 1. Clear the Strava Athlete ID column we found in your 'users' table
    conn.execute(text("UPDATE users SET strava_athlete_id = NULL;"))
    # 2. Ensure the token table is completely clean
    conn.execute(text("DELETE FROM strava_tokens;"))
    conn.commit()
    print("✅ Strava link cleared. The bot will now ask you to connect.")
