from backend.database import SessionLocal
from backend.models import User, StravaToken
import time
import sys
import os

db = SessionLocal()

# 1. Create the User record
user = User(
    name="Admin Athlete",
    telegram_chat_id=9652771023, # Your ID from above
    max_hr=190
)
db.add(user)
db.commit()
db.refresh(user)

# 2. Link the Strava Token
token = StravaToken(
    user_id=user.id,
    athlete_id=70799315,  # REPLACE THIS with your actual Strava Athlete ID
    refresh_token="8cba7fe5b1aabffc222ababe158bf753b7f74ec5", # From your strava_auth.py
    access_token="initial_sync",
    expires_at=int(time.time())
)
db.add(token)
db.commit()

print(f"🚀 Admin User created! ID: {user.id}")
print("You can now start the server and the bot will recognize you.")
