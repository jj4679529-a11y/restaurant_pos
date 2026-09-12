from fastapi import APIRouter, status

from app.api.deps import AdminUser, DbSession, Limit, Offset
from app.schemas.users import UserCreate, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(db: DbSession, _admin: AdminUser, limit: Limit = 50, offset: Offset = 0):
    return user_service.list_users(db, limit, offset)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DbSession, _admin: AdminUser):
    return user_service.create_user(db, data)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: DbSession, _admin: AdminUser):
    return user_service.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, data: UserUpdate, db: DbSession, admin: AdminUser):
    return user_service.update_user(db, user_id, data, admin.id)
