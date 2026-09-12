from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.seed.config import SeedResult
from app.seed.passwords import hash_password


def seed_admin(session: Session, username: str, password: str, name: str, result: SeedResult) -> None:
    existing = session.scalars(select(User).where(User.username == username)).one_or_none()
    if existing is not None:
        result.messages.append("Admin already exists")
        return

    session.add(
        User(
            name=name,
            username=username,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    result.admin_created = True
    result.messages.append("Admin created")
