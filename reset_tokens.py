from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Since tokens aren't in 'users', they must be here
    conn.execute(text("DELETE FROM strava_tokens;"))
    conn.commit()
    print("✅ strava_tokens table cleared. Ready for fresh login.")
