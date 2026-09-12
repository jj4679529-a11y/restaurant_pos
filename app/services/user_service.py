from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.users import UserCreate, UserUpdate
from app.services.errors import ServiceError, conflict, not_found


def list_users(session: Session, limit: int, offset: int) -> Sequence[User]:
    return session.scalars(select(User).order_by(User.id).limit(limit).offset(offset)).all()


def get_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise not_found("User")
    return user


def _commit(session: Session, user: User) -> User:
    try:
        session.add(user)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("A user with this username already exists") from exc
    session.refresh(user)
    return user


def create_user(session: Session, data: UserCreate) -> User:
    if session.scalars(select(User).where(User.username == data.username)).one_or_none() is not None:
        raise conflict("A user with this username already exists")
    return _commit(
        session,
        User(
            name=data.name,
            username=data.username,
            password_hash=hash_password(data.password),
            role=data.role,
            is_active=True,
        ),
    )


def update_user(session: Session, user_id: int, data: UserUpdate, actor_id: int) -> User:
    user = get_user(session, user_id)
    values = data.model_dump(exclude_unset=True)
    if values.get("is_active") is False and user.id == actor_id:
        raise ServiceError(
            409,
            "CANNOT_DEACTIVATE_CURRENT_USER",
            "The currently authenticated user cannot be deactivated",
        )
    username = values.get("username")
    if username is not None and session.scalars(
        select(User).where(User.username == username, User.id != user.id)
    ).one_or_none() is not None:
        raise conflict("A user with this username already exists")
    password = values.pop("password", None)
    for field, value in values.items():
        setattr(user, field, value)
    if password is not None:
        user.password_hash = hash_password(password)
    return _commit(session, user)
