from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.enums import PrintJobStatus, PrinterConnectionType, TelegramMessageType, TelegramOutboxStatus
from app.models.mixins import CreatedAtMixin, TimestampMixin
from app.models.order import Order
from app.models.types import pg_enum


class Printer(TimestampMixin, Base):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    terminal_name: Mapped[str] = mapped_column(String(64), nullable=False)
    connection_type: Mapped[PrinterConnectionType] = mapped_column(
        pg_enum(PrinterConnectionType, "printer_connection_type"),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)

    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="printer")


class PrintJob(CreatedAtMixin, Base):
    __tablename__ = "print_jobs"
    __table_args__ = (
        Index("ix_print_jobs_status", "status"),
        Index("ix_print_jobs_order_id", "order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[PrintJobStatus] = mapped_column(pg_enum(PrintJobStatus, "print_job_status"), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order] = relationship(back_populates="print_jobs")
    printer: Mapped[Printer] = relationship(back_populates="print_jobs")


class TelegramOutbox(CreatedAtMixin, Base):
    __tablename__ = "telegram_outbox"
    __table_args__ = (
        Index("ix_telegram_outbox_status", "status"),
        Index("ix_telegram_outbox_created_at", "created_at"),
        Index("ix_telegram_outbox_status_created_at", "status", "created_at"),
        Index("ix_telegram_outbox_next_attempt_at", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_type: Mapped[TelegramMessageType] = mapped_column(
        pg_enum(TelegramMessageType, "telegram_message_type"),
        nullable=False,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TelegramOutboxStatus] = mapped_column(
        pg_enum(TelegramOutboxStatus, "telegram_outbox_status"),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped[Order | None] = relationship(back_populates="telegram_messages")


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
