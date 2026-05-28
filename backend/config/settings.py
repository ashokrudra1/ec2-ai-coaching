# backend/config/settings.py - GROQ CONFIGURED VERSION
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    # App General Config
    ENVIRONMENT: str = Field(default="production", validation_alias="ENVIRONMENT")
    PORT: int = 8001
    ALLOWED_ORIGIN: str = "https://vedaactivewellness.xyz"
    DOMAIN: str = "vedaactivewellness.xyz"

    # Database & Redis Secrets
    DATABASE_URL: str = Field(..., validation_alias="DATABASE_URL")
    REPLICA_DATABASE_URL: str = Field(default="", validation_alias="REPLICA_DATABASE_URL")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    SENTRY_DSN: str = Field(default="", validation_alias="SENTRY_DSN")
    
    # Groq/OpenAI Configuration (Groq uses OpenAI-compatible API)
    OPENAI_API_KEY: SecretStr = Field(..., validation_alias="OPENAI_API_KEY")
    OPENAI_BASE_URL: str = Field(default="https://api.groq.com/openai/v1", validation_alias="OPENAI_BASE_URL")
    GROQ_API_KEY: SecretStr = Field(default="", validation_alias="OPENAI_API_KEY")  # Same as OPENAI_API_KEY
    GROQ_MODEL: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL")
    
    # Telegram Bot Token
    TELEGRAM_BOT_TOKEN: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    TELEGRAM_SECRET_TOKEN: str = Field(..., validation_alias="TELEGRAM_SECRET_TOKEN")
    
    # Strava OAuth credentials
    STRAVA_CLIENT_ID: str = Field(..., validation_alias="STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET: SecretStr = Field(..., validation_alias="STRAVA_CLIENT_SECRET")
    STRAVA_SIGNING_SECRET: str = Field(..., validation_alias="STRAVA_SIGNING_SECRET")
    STRAVA_REDIRECT_URI: str = Field(default="https://vedaactivewellness.xyz/auth/callback", validation_alias="STRAVA_REDIRECT_URI")

    # Admin Access
    ADMIN_API_KEY: SecretStr = Field(..., validation_alias="ADMIN_API_KEY")
    DEFAULT_RATE_LIMIT: str = "60 per minute"
    
    # Encryption Keys
    FIELD_ENCRYPTION_KEY: str = Field(default="", validation_alias="FIELD_ENCRYPTION_KEY")
    STRAVA_BYOK_SECRET_KEY: str = Field(default="", validation_alias="STRAVA_BYOK_SECRET_KEY")

    # Logging
    LOG_LEVEL: str = Field(default="info", validation_alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate a centralized singleton
settings = Settings()
