from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models import User, UserRole


def create_test_user(
    session: Session,
    *,
    name: str,
    username: str,
    password: str = "test-password",
    role: UserRole = UserRole.ADMIN,
    is_active: bool = True,
) -> User:
    user = User(
        name=name,
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def admin_headers(user: User) -> dict[str, str]:
    assert user.role is UserRole.ADMIN
    return auth_headers(user)


def cashier_headers(user: User) -> dict[str, str]:
    assert user.role is UserRole.CASHIER
    return auth_headers(user)
