import os
import sys

# 1. Force the Database URL so the backend doesn't crash
os.environ["DATABASE_URL"] = "postgresql://postgres:Jaipur_122@dbcoach.c94smm4quof0.ap-south-1.rds.amazonaws.com:5432/postgres"

# 2. Setup paths
sys.path.append(os.getcwd())

from backend.strava_backfill import backfill_user_history

if __name__ == "__main__":
    print("🔄 Resuming sync for User 1...")
    try:
        # This will fetch up to 600 activities
        # It skips activities already in the database (strava_id check)
        backfill_user_history(user_id=1, total_to_fetch=600)
        print("🏁 All done!")
    except Exception as e:
        print(f"❌ Sync interrupted: {e}")
