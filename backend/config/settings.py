# backend/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr

class Settings(BaseSettings):
    # App General Config
    ENVIRONMENT: str = Field(default="production", validation_alias="ENV")
    PORT: int = 8001
    ALLOWED_ORIGIN: str = "https://yourcoachingapp.com"

    # Database & Redis Secrets
    DATABASE_URL: str = Field(..., validation_alias="DATABASE_URL")
    REDIS_URL: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")
    SENTRY_DSN: str = Field(default="", validation_alias="SENTRY_DSN")
    # API Keys & Third Party Integrations
    OPENAI_API_KEY: SecretStr = Field(..., validation_alias="OPENAI_API_KEY")
    TELEGRAM_BOT_TOKEN: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    TELEGRAM_SECRET_TOKEN: str = Field(..., validation_alias="TELEGRAM_SECRET_TOKEN")
    
    # Strava OAuth credentials
    STRAVA_CLIENT_ID: str = Field(..., validation_alias="STRAVA_CLIENT_ID")
    STRAVA_CLIENT_SECRET: SecretStr = Field(..., validation_alias="STRAVA_CLIENT_SECRET")
    STRAVA_SIGNING_SECRET: str = Field(..., validation_alias="STRAVA_SIGNING_SECRET")

    # Rate Limiting & Admin Access
    ADMIN_API_KEY: SecretStr = Field(..., validation_alias="ADMIN_API_KEY")
    DEFAULT_RATE_LIMIT: str = "60 per minute"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate a centralized singleton
settings = Settings()
