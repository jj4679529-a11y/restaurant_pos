from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Setting
from app.schemas.settings import SettingUpdate
from app.services.errors import ServiceError, not_found

SECRET_SETTING_KEYS = ("ADMIN_PASSWORD", "DATABASE_URL", "JWT_SECRET_KEY", "TELEGRAM_BOT_TOKEN", "_telegram_update_offset")


def validate_setting(key, value):
    import re
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    if key == 'business_day_start' and not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', value):
        raise ServiceError(422, 'INVALID_TIME', 'Use HH:MM')
    if key == 'timezone':
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ServiceError(422, 'INVALID_TIMEZONE', 'Use an IANA timezone') from None


def list_settings(session: Session, limit: int, offset: int) -> Sequence[Setting]:
    return session.scalars(
        select(Setting)
        .where(Setting.key.not_in(SECRET_SETTING_KEYS))
        .order_by(Setting.key)
        .limit(limit)
        .offset(offset)
    ).all()


def update_setting(session: Session, key: str, data: SettingUpdate) -> Setting:
    validate_setting(key, data.value)
    if key in SECRET_SETTING_KEYS:
        raise ServiceError(400, "protected_setting", "This setting cannot be managed through the API")
    setting = session.scalars(select(Setting).where(Setting.key == key)).one_or_none()
    if setting is None:
        raise not_found("Setting")
    setting.value = data.value
    session.commit()
    session.refresh(setting)
    return setting
