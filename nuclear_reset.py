from backend.database import engine
from sqlalchemy import text

tables = [
    'strava_tokens', 
    'activities', 
    'coach_memory', 
    'athlete_insights', 
    'daily_readiness', 
    'medical_reports', 
    'performance_metrics', 
    'coaching_decisions', 
    'athlete_learnings', 
    'injury_incidents', 
    'personal_records',
    'users'
]

def nuclear_reset():
    with engine.connect() as conn:
        print("⚠️ Starting complete database wipe...")
        # Disable foreign key checks for Postgres (optional if using CASCADE)
        # conn.execute(text("SET session_replication_role = 'replica';"))
        
        for table in tables:
            try:
                # Using CASCADE to handle any foreign key dependencies
                conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
                print(f"✅ Cleared table: {table}")
            except Exception as e:
                # Check if table exists before reporting error
                print(f"⚠️ Could not clear {table} (it might not exist yet): {e}")
        
        # conn.execute(text("SET session_replication_role = 'origin';"))
        conn.commit()
        print("\n✨ Database is now empty. System is at factory settings.")

if __name__ == "__main__":
    nuclear_reset()
