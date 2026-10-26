from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "cadence-default-insecure-secret-key-change-in-prod"
    INTERNAL_SERVICE_TOKEN: str = "cadence-default-internal-token"

    # Databases
    DATABASE_URL: str = "postgresql+asyncpg://cadence:cadence_password@localhost:5432/cadence_dev"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin_secret"
    S3_REGION: str = "us-east-1"
    S3_RECORDINGS_BUCKET: str = "cadence-recordings"

    # LiveKit
    LIVEKIT_URL: str = "http://localhost:7880"
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "secret"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
