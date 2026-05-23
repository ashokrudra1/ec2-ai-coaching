from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # 1. Move all activities from User 1 to User 5
    conn.execute(text("UPDATE activities SET user_id = 5 WHERE user_id = 1;"))
    
    # 2. Move any user bios or memory if they exist
    conn.execute(text("UPDATE user_bios SET user_id = 5 WHERE user_id = 1;"))
    conn.execute(text("UPDATE coach_memory SET user_id = 5 WHERE user_id = 1;"))
    
    # 3. Now it is safe to delete the old shell account
    conn.execute(text("DELETE FROM users WHERE id = 1;"))
    
    conn.commit()
    print("✅ Success! All data moved to User 5 and User 1 deleted.")
