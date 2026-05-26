import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from backend.database import get_db
from backend.models import User
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register")
async def register_user(
    name: str, 
    email: str, 
    telegram_id: str, 
    db: Session = Depends(get_db)
):
    # 1. Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        # 2. Create the new Athlete record in RDS
        new_user = User(
           name=name,
           email=email,
           telegram_chat_id=int(telegram_id), # Ensure it's an integer
           created_at=datetime.utcnow(),
           max_hr=190,
           rest_hr=60
        )
        db.add(new_user)
        db.commit()

        db.refresh(new_user)

        # 3. Generate the Personalized Strava Auth URL using centralized logic
        from backend.strava_auth import generate_auth_link
        auth_url = generate_auth_link(str(telegram_id))

        return {
            "status": "success",
            "message": f"Welcome to VedaActive Wellness, {name}!",
            "athlete_details": {
                "user_id": new_user.id,
                "name": new_user.name,
                "telegram_id": telegram_id
            },
            "strava_link": auth_url,
            "instructions": "Copy the 'strava_link' and send it to the athlete. Once they authorize, their account will be fully linked to their specific ID."
        }

    except Exception as e:
        db.rollback()
        print(f"❌ Registration Error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
