from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting
from app.seed.catalog import SETTINGS
from app.seed.config import SeedResult


def _ensure_setting(session: Session, key: str, value: str, result: SeedResult) -> None:
    existing = session.scalars(select(Setting).where(Setting.key == key)).one_or_none()
    if existing is not None:
        return
    session.add(Setting(key=key, value=value))
    result.settings_created += 1


def seed_settings(session: Session, result: SeedResult) -> None:
    for spec in SETTINGS:
        _ensure_setting(session, spec.key, spec.value, result)
