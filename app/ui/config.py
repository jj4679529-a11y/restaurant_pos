from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path
import sys


def _resolve_project_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resolve_project_root()


class UiSettings(BaseSettings):
    """Local terminal configuration; it intentionally contains no backend secrets."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    POS_API_BASE_URL: str = "http://127.0.0.1:8000"
    POS_PRINTER_ID: int | None = Field(default=None, gt=0)
    POS_API_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, le=60)
    POS_SERVER_START_TIMEOUT_SECONDS: float = Field(default=45.0, ge=1, le=180)
    AUTO_START_WITH_WINDOWS: bool = False
