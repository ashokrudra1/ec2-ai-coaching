import requests
import sys
import os
import time

# 1. SETUP ENVIRONMENT MANUALLY
os.environ["DATABASE_URL"] = "postgresql://postgres:Jaipur_122@dbcoach.c94smm4quof0.ap-south-1.rds.amazonaws.com:5432/postgres"
sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.models import StravaToken
from backend.strava_backfill import backfill_user_history

# 2. CONFIGURATION
CLIENT_ID = "204777"
CLIENT_SECRET = "ee09ab9107866442e6b3415dd1cf03b0322fd2fb"
# GET A FRESH CODE FROM: https://www.strava.com/oauth/authorize?client_id=204777&response_type=code&redirect_uri=http://localhost&approval_prompt=force&scope=read,activity:read_all
AUTH_CODE = "6edecd1490a982d7e38b23f97ea7b40b4454092a" 

def run_migration():
    print("🔗 Attempting Strava Handshake...")
    res = requests.post('https://www.strava.com/oauth/token', data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': AUTH_CODE,
        'grant_type': 'authorization_code'
    })
    
    if res.status_code != 200:
        print(f"❌ Handshake Failed: {res.json()}")
        return

    data = res.json()
    print("✅ Handshake Success!")

    # 3. SAVE TO DATABASE
    db = SessionLocal()
    try:
        token = db.query(StravaToken).filter_by(user_id=1).first()
        if not token:
            token = StravaToken(user_id=1)
            db.add(token)
        
        token.athlete_id = data['athlete']['id']
        token.access_token = data['access_token']
        token.refresh_token = data['refresh_token']
        token.expires_at = data['expires_at']
        db.commit()
        print("💾 Tokens saved to RDS.")

        # 4. START BACKFILL
        print("🚀 Starting Sync of 540 activities (this will take ~10 mins)...")
        backfill_user_history(user_id=1, total_to_fetch=600)
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
