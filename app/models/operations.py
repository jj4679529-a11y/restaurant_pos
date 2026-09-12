from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.enums import BusinessDayStatus
from app.models.mixins import TimestampMixin
from app.models.types import pg_enum


class DeliveryWorker(TimestampMixin, Base):
    __tablename__ = "delivery_workers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="delivery_worker")


class BusinessDay(Base):
    __tablename__ = "business_days"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[BusinessDayStatus] = mapped_column(
        pg_enum(BusinessDayStatus, "business_day_status"),
        nullable=False,
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="business_day")
