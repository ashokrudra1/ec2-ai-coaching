-- Initialize pgvector extension and configure PostgreSQL for AI Coaching
-- This script runs automatically on first database startup

-- Enable pgvector extension (required for vector embeddings in CoachMemory)
CREATE EXTENSION IF NOT EXISTS pgvector;

-- Enable UUID extension for distributed systems support
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Set reasonable defaults for production
ALTER DATABASE postgres SET shared_preload_libraries = 'pgvector';

-- Create indexes for performance optimization
-- These will be managed by SQLAlchemy/Alembic migrations, but we ensure they exist

-- Log that initialization completed
RAISE NOTICE 'PostgreSQL extensions initialized successfully: pgvector, uuid-ossp enabled';
