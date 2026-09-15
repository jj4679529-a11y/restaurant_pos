from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin
from app.models.types import pg_enum


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    created_orders: Mapped[list["Order"]] = relationship(
        back_populates="creator",
        foreign_keys="Order.created_by",
    )
    cancelled_orders: Mapped[list["Order"]] = relationship(
        back_populates="canceller",
        foreign_keys="Order.cancelled_by",
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="creator")
