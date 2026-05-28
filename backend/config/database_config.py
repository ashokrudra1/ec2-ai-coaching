# backend/config/database_config.py
"""
Database Configuration Management

Centralizes database settings from environment variables.
Provides defaults and validation for connection pooling and pgvector settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class DatabaseConfig(BaseSettings):
    """
    Database configuration using Pydantic settings for environment variable management.
    
    All values can be overridden via environment variables or .env file.
    """
    
    # Primary Database (Write Operations)
    primary_database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ai_coach",
        description="PostgreSQL connection string for write operations",
        validation_alias="DATABASE_URL"
    )
    
    # Replica Database (Read Operations & Vectors)
    replica_database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL replica connection string for read operations. Defaults to primary if not set.",
        validation_alias="REPLICA_DATABASE_URL"
    )
    
    # Connection Pooling
    pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Base connection pool size"
    )
    max_overflow: int = Field(
        default=40,
        ge=0,
        le=200,
        description="Maximum overflow connections under high load"
    )
    pool_recycle: int = Field(
        default=1800,
        ge=300,
        description="Connection recycle time in seconds (prevents stale connections)"
    )
    pool_timeout: int = Field(
        default=30,
        ge=5,
        description="Timeout for pool checkout in seconds"
    )
    pool_pre_ping: bool = Field(
        default=True,
        description="Test connection health before use"
    )
    
    # SQL Logging
    sql_echo: bool = Field(
        default=False,
        description="Log all SQL statements for debugging",
        validation_alias="SQL_ECHO"
    )
    
    # pgvector Configuration
    pgvector_dimensions: int = Field(
        default=1536,
        description="Dimension size for pgvector embeddings (e.g., 1536 for OpenAI embeddings)"
    )
    pgvector_enabled: bool = Field(
        default=True,
        description="Enable pgvector extension initialization"
    )
    
    # Session Configuration
    autocommit: bool = Field(
        default=False,
        description="SQLAlchemy session autocommit behavior"
    )
    autoflush: bool = Field(
        default=False,
        description="SQLAlchemy session autoflush behavior"
    )
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    def get_replica_url(self) -> str:
        """
        Get replica database URL, falling back to primary if not configured.
        
        Returns:
            Replica URL or primary URL if replica not configured
        """
        return self.replica_database_url or self.primary_database_url
    
    def to_engine_kwargs(self) -> dict:
        """
        Convert configuration to SQLAlchemy engine creation kwargs.
        
        Returns:
            Dictionary of engine kwargs for create_engine()
        """
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_recycle": self.pool_recycle,
            "pool_timeout": self.pool_timeout,
            "pool_pre_ping": self.pool_pre_ping,
            "echo": self.sql_echo,
        }
    
    def to_session_kwargs(self) -> dict:
        """
        Convert configuration to SQLAlchemy session factory kwargs.
        
        Returns:
            Dictionary of session kwargs for sessionmaker()
        """
        return {
            "autocommit": self.autocommit,
            "autoflush": self.autoflush,
        }


# Instantiate singleton configuration
database_config = DatabaseConfig()
