from dataclasses import dataclass, field

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from app.core.config import PROJECT_ROOT


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    ADMIN_USERNAME: str
    # Keep legacy blank bootstrap passwords valid; they are always hashed and
    # the login flow can verify an existing blank-password admin hash.
    ADMIN_PASSWORD: str = ""
    ADMIN_NAME: str = "Administrator"
    OSH_HALF_PRICE: int | None = Field(default=None, gt=0)
    OSH_FULL_PRICE: int | None = Field(default=None, gt=0)
    EGG_ONE_PRICE: int | None = Field(default=None, gt=0)
    EGG_TWO_PRICE: int | None = Field(default=None, gt=0)
    QAZI_PRICE: int | None = Field(default=None, gt=0)
    GOSHT_MANUAL_PRESETS: list[int] = Field(default_factory=list)
    JIZZ_MANUAL_PRESETS: list[int] = Field(default_factory=list)


@dataclass
class SeedResult:
    admin_created: bool
    categories_created: int = 0
    products_created: int = 0
    price_options_created: int = 0
    addons_created: int = 0
    product_addons_created: int = 0
    delivery_workers_created: int = 0
    settings_created: int = 0
    messages: list[str] = field(default_factory=list)
