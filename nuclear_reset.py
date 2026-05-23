from backend.database import engine
from sqlalchemy import text

tables = ['strava_tokens', 'activities', 'user_bios', 'coach_memory', 'users']

with engine.connect() as conn:
    print("⚠️ Starting complete database wipe...")
    for table in tables:
        try:
            # Using CASCADE to handle any foreign key dependencies
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            print(f"✅ Cleared table: {table}")
        except Exception as e:
            print(f"❌ Could not clear {table}: {e}")
    conn.commit()
    print("\n✨ Database is now empty. System is at factory settings.")
