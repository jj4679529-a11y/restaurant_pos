from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models import User, UserRole
from app.services.errors import ServiceError

DbSession = Annotated[Session, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    if credentials is None:
        raise ServiceError(401, "AUTHENTICATION_REQUIRED", "Bearer access token is required")
    user_id, _token_role = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise ServiceError(401, "INVALID_TOKEN", "Access token user no longer exists")
    if not user.is_active:
        raise ServiceError(403, "USER_INACTIVE", "User account is inactive")
    return user


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role is not UserRole.ADMIN:
        raise ServiceError(403, "FORBIDDEN", "Administrator permission is required")
    return current_user


def require_cashier_or_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if current_user.role not in (UserRole.ADMIN, UserRole.CASHIER):
        raise ServiceError(403, "FORBIDDEN", "Cashier or administrator permission is required")
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
CashierOrAdminUser = Annotated[User, Depends(require_cashier_or_admin)]
