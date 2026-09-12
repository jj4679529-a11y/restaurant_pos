from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models import User
from app.services.errors import ServiceError


@dataclass(frozen=True)
class AuthenticationResult:
    user: User
    access_token: str


def authenticate(session: Session, username: str, password: str) -> AuthenticationResult:
    user = session.scalars(select(User).where(User.username == username.strip())).one_or_none()
    if user is None:
        raise ServiceError(401, "INVALID_CREDENTIALS", "Username or password is incorrect")
    try:
        password_matches = verify_password(password, user.password_hash)
    except Exception:
        password_matches = False
    if not password_matches:
        raise ServiceError(401, "INVALID_CREDENTIALS", "Username or password is incorrect")
    if not user.is_active:
        raise ServiceError(403, "USER_INACTIVE", "User account is inactive")
    return AuthenticationResult(user=user, access_token=create_access_token(user))
