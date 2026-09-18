from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.mixins import TimestampMixin


class DailyReport(Base, TimestampMixin):
    __tablename__ = "daily_reports"

    __table_args__ = (
        UniqueConstraint(
            "business_date",
            name="uq_daily_reports_business_date",
        ),
        Index(
            "ix_daily_reports_business_date",
            "business_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    business_day_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "business_days.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    business_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    snapshot: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    printer_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "printers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    total_paid_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    paid_order_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    cancelled_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    chaykhana_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    delivery_amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )

    is_latest: Mapped[bool] = mapped_column(
        default=True,
        server_default="true",
        nullable=False,
    )

    business_day = relationship(
        "BusinessDay",
        lazy="joined",
    )
