"""
Centralized application settings.
All configuration is loaded from environment variables / .env file.
Nothing here is hard-coded — see .env.example for the full list.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "GuardianAI"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./guardianai.db"

    # Security
    SECRET_KEY: str = "CHANGE_ME_TO_A_LONG_RANDOM_STRING"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Email (used starting Phase 3)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""

    # Telegram (optional, Phase 3+)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Escalation timing (Phase 3). Real-world defaults are minutes, but the
    # spec calls for a live viva demo, so defaults here are short (seconds).
    # Override in .env for a more realistic 5/10-minute chain in production.
    # Step 0 (notify caretaker) fires immediately at emergency creation.
    ESCALATION_STEP1_DELAY_SECONDS: int = 60   # unacknowledged -> notify family
    ESCALATION_STEP2_DELAY_SECONDS: int = 120  # unacknowledged + CRITICAL -> notify doctor
    ESCALATION_CHECK_INTERVAL_SECONDS: int = 15  # how often the background scheduler ticks

    # Video/image upload (Phase 4)
    UPLOAD_DIR: str = "../data/uploads"
    EVIDENCE_DIR: str = "../data/evidence"
    MAX_UPLOAD_SIZE_MB: int = 100


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance so we don't re-parse .env on every import."""
    return Settings()


settings = get_settings()
