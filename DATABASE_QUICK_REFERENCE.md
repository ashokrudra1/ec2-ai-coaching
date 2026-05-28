# Database Layer Quick Reference

## Import Statements

```python
# Primary database session
from backend.database import get_session, SessionLocal

# Replica database session
from backend.database import get_replica_session, ReplicaSessionLocal

# Scoped (thread-local) sessions
from backend.database import get_scoped_session, scoped_session_factory
from backend.database import get_scoped_replica_session, scoped_replica_session_factory

# Models
from backend.models import User, Activity, CoachMemory, AthleteInsight

# Configuration
from backend.config.database_config import database_config

# Utilities
from backend.database import initialize_database, health_check, cleanup_scoped_sessions
```

## Context Manager Patterns

### Pattern 1: Simple Query (Read)
```python
from backend.database import get_replica_session
from backend.models import User

with get_replica_session() as session:
    user = session.query(User).filter_by(id=1).first()
    print(user.name)
```

### Pattern 2: Create/Update (Write)
```python
from backend.database import get_session
from backend.models import Activity

with get_session() as session:
    activity = Activity(
        user_id=1,
        name="Morning Run",
        distance_km=10.5,
        start_date_utc=datetime.now()
    )
    session.add(activity)
    session.commit()
    print(f"Created activity: {activity.id}")
```

### Pattern 3: Batch Operations
```python
from backend.database import get_session
from backend.models import PerformanceMetric

with get_session() as session:
    metrics = [
        PerformanceMetric(user_id=1, weekly_tss=250.0),
        PerformanceMetric(user_id=2, weekly_tss=300.0),
    ]
    session.add_all(metrics)
    session.commit()
```

### Pattern 4: Scoped Session (Celery Tasks)
```python
from backend.database import get_scoped_session

@shared_task
def process_data(user_id: int):
    with get_scoped_session() as session:
        # Runs in worker thread
        # Session automatically cleaned up via remove()
        pass
```

### Pattern 5: Vector Search
```python
from backend.database import get_replica_session
from backend.models import CoachMemory

with get_replica_session() as session:
    query_vector = [0.1, 0.2, ..., 1536 floats]
    
    memories = session.query(CoachMemory)\
        .filter(CoachMemory.user_id == 1)\
        .order_by(
            CoachMemory.vector_embedding.cosine_distance(query_vector)
        )\
        .limit(5)\
        .all()
```

## FastAPI Dependency Injection

### Old Way (❌ Don't use)
```python
from backend.database import SessionLocal

@app.get("/users/{user_id}")
def get_user(user_id: int):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        return user
    finally:
        db.close()  # Manual cleanup
```

### New Way (✅ Use context managers)
```python
from backend.database import get_session

@app.get("/users/{user_id}")
def get_user(user_id: int):
    with get_session() as db:
        user = db.query(User).filter_by(id=user_id).first()
        return user  # Auto cleanup on exit
```

### With FastAPI Dependency
```python
from fastapi import FastAPI, Depends
from backend.database import get_session

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int, db = Depends(get_session)):
    user = db.query(User).filter_by(id=user_id).first()
    return user
```

## Application Startup/Shutdown

```python
from fastapi import FastAPI
from backend.database import initialize_database, cleanup_scoped_sessions

app = FastAPI()

@app.on_event("startup")
async def startup():
    print("🔧 Initializing database...")
    initialize_database()
    print("✅ Database ready")

@app.on_event("shutdown")
async def shutdown():
    print("🧹 Cleaning up sessions...")
    cleanup_scoped_sessions()
    print("✅ Cleanup complete")
```

## Configuration Usage

```python
from backend.config.database_config import database_config

# Check current settings
print(f"Pool size: {database_config.pool_size}")
print(f"Max overflow: {database_config.max_overflow}")
print(f"Connection recycle: {database_config.pool_recycle}s")
print(f"pgvector dimensions: {database_config.pgvector_dimensions}")

# Get engine kwargs for custom engine
engine_kwargs = database_config.to_engine_kwargs()

# Get session kwargs for custom session factory
session_kwargs = database_config.to_session_kwargs()
```

## Sports Science Fields (User Model)

```python
from backend.models import User
from backend.database import get_session

with get_session() as session:
    user = session.query(User).filter_by(id=1).first()
    
    # Training Stress
    print(f"Chronic Training Load (CTL): {user.ctl}")  # 42-day
    print(f"Acute Training Load (ATL): {user.atl}")    # 7-day
    print(f"Training Stress Balance: {user.tsb}")      # CTL - ATL
    
    # Periodization
    print(f"Training Phase: {user.training_phase}")    # Base/Build/Peak/Taper
    print(f"Macrocycle Week: {user.macrocycle_week}")
    print(f"Target Weekly TSS: {user.target_weekly_tss}")
    
    # Dynamic Twins (JSONB)
    print(f"Confidence: {user.psychological_twin['confidence']}")
    print(f"Compliance: {user.behavioral_twin['compliance_rate']}")
    print(f"VO2max: {user.physiological_twin['vo2max_estimate']}")
```

## Vector Embeddings (CoachMemory Model)

```python
from backend.models import CoachMemory
from backend.database import get_session

with get_session() as session:
    memory = CoachMemory(
        user_id=1,
        role="assistant",
        content="Great effort on today's workout!",
        category="encouragement",
        vector_embedding=[0.1, 0.2, ..., 1536 floats],
        memory_salience=0.95,
        metadata={
            "tags": ["positive", "motivation"],
            "related_activity_id": 123
        }
    )
    session.add(memory)
    session.commit()
    print(f"Memory created: {memory.id}")
```

## Health Checks

```python
from backend.database import health_check

if health_check():
    print("✅ Database is healthy")
else:
    print("❌ Database is not responding")
```

## Common Queries

### Get All Activities for User
```python
from backend.database import get_replica_session
from backend.models import Activity

with get_replica_session() as session:
    activities = session.query(Activity)\
        .filter_by(user_id=1)\
        .order_by(Activity.start_date_utc.desc())\
        .all()
```

### Get Recent Insights
```python
from backend.database import get_replica_session
from backend.models import AthleteInsight

with get_replica_session() as session:
    insights = session.query(AthleteInsight)\
        .filter_by(user_id=1, is_active=True)\
        .order_by(AthleteInsight.created_at.desc())\
        .limit(10)\
        .all()
```

### Get User with All Relations
```python
from backend.database import get_replica_session
from sqlalchemy.orm import joinedload
from backend.models import User

with get_replica_session() as session:
    user = session.query(User)\
        .options(
            joinedload(User.activities),
            joinedload(User.memories),
            joinedload(User.insights)
        )\
        .filter_by(id=1)\
        .first()
```

## Error Handling

### Commit Failures
```python
from backend.database import get_session
from sqlalchemy.exc import IntegrityError

with get_session() as session:
    try:
        # Attempt operation
        session.add(obj)
        session.commit()
    except IntegrityError as e:
        session.rollback()
        print(f"Constraint violation: {e}")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
```

### Connection Errors
```python
from backend.database import get_session
from sqlalchemy.exc import OperationalError

try:
    with get_session() as session:
        result = session.query(User).first()
except OperationalError as e:
    print(f"Connection error: {e}")
    # Implement retry logic or fallback
```

---

## Environment Variables

Set in `.env`:
```env
# Primary database
DATABASE_URL=postgresql://user:password@localhost:5432/ai_coach

# Replica (optional, falls back to primary)
REPLICA_DATABASE_URL=postgresql://user:password@replica:5432/ai_coach

# SQL logging (for debugging)
SQL_ECHO=false
```

---

## Verification

Run verification script:
```bash
python backend/verify_imports.py
```

Expected output: ✅ ALL VERIFICATIONS PASSED
