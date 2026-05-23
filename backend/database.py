# backend/database.py
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

# Primary DB for Writes, Replicas for intensive Analytical/Vector Reads
PRIMARY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ai_coach")
REPLICA_DATABASE_URL = os.getenv("REPLICA_DATABASE_URL", PRIMARY_DATABASE_URL)

# Hardened Connection Pooling
engine = create_engine(
    PRIMARY_DATABASE_URL,
    pool_size=20,          # Increase base connections
    max_overflow=40,       # Allow burst connections under high load
    pool_recycle=1800,     # Recycle connections every 30 mins to prevent memory leaks
    pool_timeout=30,       # Fail fast if pool is saturated
    pool_pre_ping=True     # Actively test connection health before returning it
)

replica_engine = create_engine(
    REPLICA_DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_recycle=1800,
    pool_timeout=30,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReplicaSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=replica_engine)

Base = declarative_base()

def get_db():
    """Default transactional database session (Primary - Write)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_replica_db():
    """Analytical read-only session (Replica - Reads/Vectors)."""
    db = ReplicaSessionLocal()
    try:
        yield db
    finally:
        db.close()
