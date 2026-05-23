from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # This forces the bot to show the "Connect Strava" button again
    conn.execute(text("UPDATE users SET strava_athlete_id = NULL WHERE id = 5;"))
    conn.execute(text("DELETE FROM strava_tokens;"))
    conn.commit()
    print("✅ System reset. Now restart the service and use /start in Telegram.")
