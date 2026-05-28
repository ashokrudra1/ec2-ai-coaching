#!/usr/bin/env python
"""
Verification script to ensure no circular imports and all dependencies load correctly.
Run this after making changes to database.py or models.py
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def verify_imports():
    """Verify all critical imports load without circular dependencies"""
    
    logger.info("=" * 70)
    logger.info("VERIFYING DATABASE LAYER IMPORTS")
    logger.info("=" * 70)
    
    try:
        logger.info("1️⃣ Importing database module...")
        from backend import database
        logger.info("   ✅ backend.database imported successfully")
        
        logger.info("2️⃣ Importing models module...")
        from backend import models
        logger.info("   ✅ backend.models imported successfully")
        
        logger.info("3️⃣ Verifying scoped_session factories...")
        assert hasattr(database, 'scoped_session_factory'), "Missing scoped_session_factory"
        assert hasattr(database, 'scoped_replica_session_factory'), "Missing scoped_replica_session_factory"
        logger.info("   ✅ Scoped session factories exist")
        
        logger.info("4️⃣ Verifying context managers...")
        assert hasattr(database, 'get_session'), "Missing get_session context manager"
        assert hasattr(database, 'get_replica_session'), "Missing get_replica_session context manager"
        assert hasattr(database, 'get_scoped_session'), "Missing get_scoped_session context manager"
        assert hasattr(database, 'get_scoped_replica_session'), "Missing get_scoped_replica_session context manager"
        logger.info("   ✅ All context managers exist")
        
        logger.info("5️⃣ Verifying cleanup function...")
        assert hasattr(database, 'cleanup_scoped_sessions'), "Missing cleanup_scoped_sessions function"
        logger.info("   ✅ Cleanup function exists")
        
        logger.info("6️⃣ Verifying model classes...")
        assert hasattr(models, 'User'), "Missing User model"
        assert hasattr(models, 'Activity'), "Missing Activity model"
        assert hasattr(models, 'CoachMemory'), "Missing CoachMemory model"
        assert hasattr(models, 'AthleteInsight'), "Missing AthleteInsight model"
        logger.info("   ✅ All required models exist")
        
        logger.info("7️⃣ Verifying pgvector support...")
        from sqlalchemy.dialects.postgresql import JSONB
        from pgvector.sqlalchemy import Vector
        logger.info("   ✅ pgvector and JSONB support available")
        
        logger.info("8️⃣ Importing config...")
        from backend.config import database_config
        logger.info("   ✅ database_config imported successfully")
        
        logger.info("9️⃣ Verifying database configuration...")
        assert hasattr(database_config, 'database_config'), "Missing database_config instance"
        config = database_config.database_config
        assert config.pool_size == 20, f"Expected pool_size=20, got {config.pool_size}"
        assert config.max_overflow == 40, f"Expected max_overflow=40, got {config.max_overflow}"
        assert config.pool_recycle == 1800, f"Expected pool_recycle=1800, got {config.pool_recycle}"
        logger.info("   ✅ Configuration values verified")
        
        logger.info("=" * 70)
        logger.info("✅ ALL VERIFICATIONS PASSED")
        logger.info("=" * 70)
        return True
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"❌ VERIFICATION FAILED: {str(e)}")
        logger.error("=" * 70)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = verify_imports()
    sys.exit(0 if success else 1)
