from functools import lru_cache
from pathlib import Path
import sys

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.runtime_paths import configuration_file


def _resolve_project_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resolve_project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=configuration_file(PROJECT_ROOT),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    APP_NAME: str = "Restaurant POS"
    APP_ENV: str = "development"
    DEBUG: bool = False
    PRODUCT_MEDIA_DIR: Path = PROJECT_ROOT / "media" / "products"
    JWT_SECRET_KEY: str | None = None
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=720, ge=1)
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None
    TELEGRAM_ADMIN_CHAT_ID: str | None = None
    TELEGRAM_ENABLED: bool = False
    TELEGRAM_DAILY_REPORT_TIME: str | None = None
    TELEGRAM_OUTBOX_BATCH_SIZE: int = Field(default=50, ge=1, le=100)


@lru_cache
def get_settings() -> Settings:
    return Settings()
