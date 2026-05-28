# backend/database.py
import os
import logging
import time
from contextlib import contextmanager
from sqlalchemy import create_engine, text, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
PRIMARY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_coach")
REPLICA_DATABASE_URL = os.getenv("REPLICA_DATABASE_URL", PRIMARY_DATABASE_URL)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "40"))
DB_POOL_RECYCLE_SECONDS = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
DB_POOL_TIMEOUT_SECONDS = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))

# Validate that DATABASE_URL is set and properly formatted
if not PRIMARY_DATABASE_URL or PRIMARY_DATABASE_URL.endswith("[REDACTED]"):
    logger.warning("DATABASE_URL appears to be unset or redacted. Using localhost fallback.")
    PRIMARY_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"

# ============================================================================
# PRIMARY ENGINE (WRITE OPERATIONS)
# ============================================================================
engine = create_engine(
    PRIMARY_DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_recycle=DB_POOL_RECYCLE_SECONDS,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
    pool_pre_ping=True,              # Test connection health before use
    echo=os.getenv("SQL_ECHO", "false").lower() == "true"  # Optional: log SQL
)

# ============================================================================
# REPLICA ENGINE (READ OPERATIONS & VECTORS)
# ============================================================================
replica_engine = create_engine(
    REPLICA_DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_recycle=DB_POOL_RECYCLE_SECONDS,
    pool_timeout=DB_POOL_TIMEOUT_SECONDS,
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true"
)

# ============================================================================
# SESSION FACTORIES
# ============================================================================
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReplicaSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=replica_engine)

# ============================================================================
# SCOPED SESSIONS (THREAD-LOCAL STORAGE)
# ============================================================================
# Scoped sessions provide thread-local storage for sessions.
# Useful in multi-threaded environments to maintain one session per thread.
scoped_session_factory = scoped_session(SessionLocal)
scoped_replica_session_factory = scoped_session(ReplicaSessionLocal)

# ============================================================================
# BASE FOR ORM MODELS
# ============================================================================
Base = declarative_base()


# ============================================================================
# CONTEXT MANAGERS FOR AUTOMATIC SESSION CLEANUP
# ============================================================================
@contextmanager
def get_session():
    """
    Context manager for obtaining a primary database session with automatic cleanup.
    
    Usage:
        with get_session() as session:
            session.query(User).filter_by(id=1).first()
    
    Automatically closes the session on context exit.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_replica_session():
    """
    Context manager for obtaining a replica database session with automatic cleanup.
    Useful for read-heavy operations and vector searches.
    
    Usage:
        with get_replica_session() as session:
            session.query(CoachMemory).all()
    
    Automatically closes the session on context exit.
    """
    session = ReplicaSessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def get_scoped_session():
    """
    Context manager for obtaining a thread-local scoped session.
    
    Usage:
        with get_scoped_session() as session:
            session.query(User).all()
    
    For use in multi-threaded environments. Automatically removes
    the session registry entry on context exit.
    """
    session = scoped_session_factory()
    try:
        yield session
    finally:
        scoped_session_factory.remove()


@contextmanager
def get_scoped_replica_session():
    """
    Context manager for obtaining a thread-local scoped replica session.
    
    Usage:
        with get_scoped_replica_session() as session:
            session.query(CoachMemory).all()
    
    For use in multi-threaded environments. Automatically removes
    the session registry entry on context exit.
    """
    session = scoped_replica_session_factory()
    try:
        yield session
    finally:
        scoped_replica_session_factory.remove()



# ============================================================================
# CONNECTION EVENT HANDLERS FOR DEBUGGING
# ============================================================================
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log successful connections"""
    logger.debug("PostgreSQL connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkouts from pool"""
    logger.debug("Connection checked out from pool")


# ============================================================================
# SESSION CLEANUP UTILITIES
# ============================================================================
def cleanup_scoped_sessions():
    """
    Clean up all scoped session registries.
    
    Call this during application shutdown to ensure proper resource cleanup.
    """
    logger.info("Cleaning up scoped sessions...")
    try:
        scoped_session_factory.remove()
        scoped_replica_session_factory.remove()
        logger.info("✅ Scoped sessions cleaned up successfully")
    except Exception as e:
        logger.error(f"⚠️ Error during scoped session cleanup: {str(e)}")


# ============================================================================
# DEPENDENCY INJECTION FOR FASTAPI
# ============================================================================
def get_db():
    """
    Default transactional database session (Primary - Write operations).
    Use this for most operations that involve mutations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_replica_db():
    """
    Analytical read-only session (Replica - Reads/Vectors).
    Use this for heavy analytical queries and vector searches to
    distribute load away from the primary writer.
    """
    db = ReplicaSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# DATABASE INITIALIZATION & MIGRATION FUNCTIONS
# ============================================================================
def wait_for_database(max_retries: int = 30, retry_interval: int = 2):
    """
    Wait for PostgreSQL to become available and ready for connections.
    
    This is called during application startup to ensure the database
    is accessible before proceeding with migrations.
    
    Args:
        max_retries: Maximum number of connection attempts
        retry_interval: Seconds to wait between retries
    
    Returns:
        True if database is ready, raises Exception if timeout
    """
    logger.info("🔄 Waiting for PostgreSQL to become available...")
    
    for attempt in range(max_retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info(f"✅ PostgreSQL is ready (attempt {attempt + 1}/{max_retries})")
                return True
        except Exception as e:
            remaining = max_retries - attempt - 1
            if remaining > 0:
                logger.warning(
                    f"⏳ PostgreSQL not ready yet (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {retry_interval}s... Error: {str(e)}"
                )
                time.sleep(retry_interval)
            else:
                logger.error(f"❌ PostgreSQL failed to become ready after {max_retries} attempts")
                raise Exception(f"Database connection failed: {str(e)}")
    
    return False


def ensure_pgvector_extension():
    """
    Ensure pgvector extension is created in PostgreSQL.
    This is required for vector embeddings in CoachMemory model.
    """
    logger.info("🔍 Checking pgvector extension...")
    try:
        with engine.connect() as conn:
            # Check if extension exists
            result = conn.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pgvector'")
            ).scalar()
            
            if result is None:
                logger.info("📦 Creating pgvector extension...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgvector"))
                conn.commit()
                logger.info("✅ pgvector extension created successfully")
            else:
                logger.info("✅ pgvector extension already exists")
    except Exception as e:
        logger.error(f"❌ Failed to ensure pgvector extension: {str(e)}")
        raise


def create_all_tables():
    """
    Create all SQLAlchemy ORM tables if they don't exist.
    Uses Base.metadata.create_all() for immediate table creation.
    
    This is a fallback for when Alembic migrations haven't run yet
    or are not being used. In production, prefer Alembic migrations.
    """
    logger.info("🗂️ Creating database tables (if not already present)...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {str(e)}")
        raise


def run_alembic_migrations():
    """
    Run Alembic migrations to ensure database schema is up to date.
    
    This function attempts to run pending migrations automatically.
    If Alembic is not available or configured, it falls back to
    Base.metadata.create_all() for table creation.
    """
    logger.info("🚀 Attempting to run Alembic migrations...")
    try:
        from alembic.config import Config
        from alembic import command
        
        # Construct path to alembic.ini
        alembic_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        alembic_ini_path = os.path.join(alembic_dir, "alembic.ini")
        
        if not os.path.exists(alembic_ini_path):
            logger.warning(f"⚠️ alembic.ini not found at {alembic_ini_path}")
            logger.info("📝 Falling back to create_all_tables()...")
            create_all_tables()
            return
        
        # Configure Alembic with current DATABASE_URL
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", PRIMARY_DATABASE_URL)
        
        # Run upgrade to head
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Alembic migrations completed successfully")
        
    except ImportError:
        logger.warning("⚠️ Alembic not installed or import failed")
        logger.info("📝 Falling back to create_all_tables()...")
        create_all_tables()
    except Exception as e:
        logger.warning(f"⚠️ Alembic migration failed: {str(e)}")
        logger.info("📝 Falling back to create_all_tables()...")
        try:
            create_all_tables()
        except Exception as fallback_error:
            logger.error(f"❌ Both Alembic and create_all_tables failed: {str(fallback_error)}")
            raise


def initialize_database():
    """
    Complete database initialization sequence.
    
    This function should be called during application startup:
    1. Wait for PostgreSQL to be available
    2. Ensure pgvector extension is installed
    3. Run migrations (Alembic) or create tables as fallback
    
    Raises:
        Exception: If any critical step fails
    """
    logger.info("=" * 70)
    logger.info("🔧 INITIALIZING DATABASE...")
    logger.info("=" * 70)
    
    try:
        # Step 1: Wait for database to be ready
        wait_for_database()
        
        # Step 2: Ensure pgvector extension
        ensure_pgvector_extension()
        
        # Step 3: Run migrations or create tables
        run_alembic_migrations()
        
        logger.info("=" * 70)
        logger.info("✅ DATABASE INITIALIZATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"❌ DATABASE INITIALIZATION FAILED: {str(e)}")
        logger.error("=" * 70)
        raise


def health_check() -> bool:
    """
    Perform a quick health check on the database connection.
    
    Returns:
        True if database is healthy, False otherwise
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False
