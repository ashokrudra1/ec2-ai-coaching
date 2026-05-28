#!/usr/bin/env python
"""
Database initialization and migration utility for Veda AI Coaching.

Usage:
    python scripts/init_database.py         # Full initialization
    python scripts/init_database.py --check # Check current state
    python scripts/init_database.py --reset # Reset (dangerous - full reset)
"""
import os
import sys
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import (
    initialize_database,
    wait_for_database,
    ensure_pgvector_extension,
    create_all_tables,
    engine,
    Base
)
from dotenv import load_dotenv
from sqlalchemy import text, inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


def check_database_state():
    """Check current database state and report tables/extensions"""
    logger.info("🔍 Checking database state...")
    
    try:
        with engine.connect() as conn:
            # Check extensions
            extensions = conn.execute(
                text("SELECT extname FROM pg_extension")
            ).fetchall()
            
            logger.info(f"📦 Installed extensions: {[ext[0] for ext in extensions]}")
            
            # Check tables
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if not tables:
                logger.warning("⚠️  No tables found in database")
            else:
                logger.info(f"📊 Database tables ({len(tables)}): {', '.join(tables)}")
            
            return True
    except Exception as e:
        logger.error(f"❌ Failed to check database state: {str(e)}")
        return False


def reset_database():
    """Reset database - DROP all tables and recreate"""
    logger.warning("🚨 WARNING: This will DROP all database tables!")
    response = input("Type 'reset' to confirm: ")
    
    if response != "reset":
        logger.info("Reset cancelled")
        return False
    
    try:
        logger.info("🗑️  Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        logger.info("✅ Tables dropped")
        
        logger.info("🔄 Creating fresh schema...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Fresh schema created")
        
        return True
    except Exception as e:
        logger.error(f"❌ Reset failed: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Initialize and manage Veda AI Coaching database"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check database state without making changes"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (DROP all tables and recreate)"
    )
    
    args = parser.parse_args()
    
    if args.check:
        return check_database_state()
    elif args.reset:
        return reset_database()
    else:
        # Default: full initialization
        try:
            initialize_database()
            logger.info("✅ Database initialization successful")
            check_database_state()
            return True
        except Exception as e:
            logger.error(f"❌ Initialization failed: {str(e)}")
            return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
