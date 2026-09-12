from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.models import User, UserRole
from app.services.errors import ServiceError

_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return _password_hash.verify(plain_password, password_hash)


def _jwt_settings() -> tuple[str, str, int]:
    settings = get_settings()
    if not settings.JWT_SECRET_KEY:
        raise ServiceError(
            503,
            "AUTH_CONFIGURATION_ERROR",
            "JWT_SECRET_KEY must be configured before authentication can be used",
        )
    return settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM, settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES


def create_access_token(user: User, now: datetime | None = None) -> str:
    secret, algorithm, lifetime_minutes = _jwt_settings()
    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        raise ValueError("Token issue time must be timezone-aware")
    issued_at = issued_at.astimezone(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "iat": issued_at,
            "exp": issued_at + timedelta(minutes=lifetime_minutes),
        },
        secret,
        algorithm=algorithm,
    )


def decode_access_token(token: str) -> tuple[int, UserRole]:
    secret, algorithm, _ = _jwt_settings()
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except ExpiredSignatureError as exc:
        raise ServiceError(401, "TOKEN_EXPIRED", "Access token has expired") from exc
    except InvalidTokenError as exc:
        raise ServiceError(401, "INVALID_TOKEN", "Access token is invalid") from exc

    subject = payload.get("sub")
    role = payload.get("role")
    try:
        user_id = int(subject)
        token_role = UserRole(role)
    except (TypeError, ValueError) as exc:
        raise ServiceError(401, "INVALID_TOKEN", "Access token claims are invalid") from exc
    if user_id <= 0:
        raise ServiceError(401, "INVALID_TOKEN", "Access token claims are invalid")
    return user_id, token_role
