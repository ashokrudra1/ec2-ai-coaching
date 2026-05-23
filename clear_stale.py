from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("DELETE FROM strava_tokens;"))
    conn.execute(text("UPDATE users SET strava_athlete_id = NULL;"))
    conn.commit()
    print("✅ Database cleared of stale tokens.")
