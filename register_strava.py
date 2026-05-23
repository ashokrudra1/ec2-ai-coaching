import requests
import os
from dotenv import load_dotenv

load_dotenv()

client_id = os.getenv("STRAVA_CLIENT_ID")
client_secret = os.getenv("STRAVA_CLIENT_SECRET")

# 1. View existing subscriptions
subs = requests.get(
    f"https://www.strava.com/api/v3/push_subscriptions?client_id={client_id}&client_secret={client_secret}"
)
print(f"Current Subscriptions: {subs.json()}")

# 2. Delete them
for sub in subs.json():
    del_res = requests.delete(
        f"https://www.strava.com/api/v3/push_subscriptions/{sub['id']}?client_id={client_id}&client_secret={client_secret}"
    )
    print(f"Deleted {sub['id']}: {del_res.status_code}")
