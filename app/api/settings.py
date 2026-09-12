from fastapi import APIRouter

from app.api.deps import AdminUser, DbSession, Limit, Offset
from app.schemas.settings import SettingResponse, SettingUpdate
from app.services import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingResponse], description="List public operational settings; environment secrets are never stored here.")
def list_settings(db: DbSession, _admin: AdminUser, limit: Limit = 50, offset: Offset = 0):
    return settings_service.list_settings(db, limit, offset)


@router.patch("/{key}", response_model=SettingResponse)
def update_setting(key: str, data: SettingUpdate, db: DbSession, _admin: AdminUser):
    return settings_service.update_setting(db, key, data)
