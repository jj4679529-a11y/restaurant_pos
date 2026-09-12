from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.catalog import AddOn, PriceOption, Product
from app.models.enums import OrderType, PaymentStatus
from app.models.mixins import CreatedAtMixin, TimestampMixin
from app.models.operations import BusinessDay, DeliveryWorker
from app.models.types import pg_enum
from app.models.user import User


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(
            "(order_type <> 'DELIVERY') OR (delivery_worker_id IS NOT NULL)",
            name="ck_orders_delivery_requires_worker",
        ),
        CheckConstraint(
            "(order_type <> 'CHAYKHANA') OR (delivery_worker_id IS NULL)",
            name="ck_orders_chaykhana_without_worker",
        ),
        Index("ix_orders_business_day_id", "business_day_id"),
        Index("ix_orders_payment_status", "payment_status"),
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_order_type", "order_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    business_day_id: Mapped[int] = mapped_column(
        ForeignKey("business_days.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_type: Mapped[OrderType] = mapped_column(pg_enum(OrderType, "order_type"), nullable=False)
    delivery_worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("delivery_workers.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        pg_enum(PaymentStatus, "payment_status"),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)

    business_day: Mapped[BusinessDay] = relationship(back_populates="orders")
    delivery_worker: Mapped[DeliveryWorker | None] = relationship(back_populates="orders")
    creator: Mapped[User] = relationship(back_populates="created_orders", foreign_keys=[created_by])
    canceller: Mapped[User | None] = relationship(back_populates="cancelled_orders", foreign_keys=[cancelled_by])
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    payments: Mapped[list["Payment"]] = relationship(back_populates="order")
    print_jobs: Mapped[list["PrintJob"]] = relationship(back_populates="order")
    telegram_messages: Mapped[list["TelegramOutbox"]] = relationship(back_populates="order")


class OrderItem(CreatedAtMixin, Base):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order_id", "order_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_price_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("price_options.id", ondelete="RESTRICT"),
        nullable=True,
    )
    manual_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()
    selected_price_option: Mapped[PriceOption | None] = relationship()
    addons: Mapped[list["OrderItemAddOn"]] = relationship(back_populates="order_item")


class OrderItemAddOn(CreatedAtMixin, Base):
    __tablename__ = "order_item_addons"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_item_id: Mapped[int] = mapped_column(
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    addon_id: Mapped[int] = mapped_column(ForeignKey("add_ons.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    price_option_id: Mapped[int | None] = mapped_column(
        ForeignKey("price_options.id", ondelete="RESTRICT"),
        nullable=True,
    )
    manual_price: Mapped[int | None] = mapped_column(Integer, nullable=True)

    order_item: Mapped[OrderItem] = relationship(back_populates="addons")
    addon: Mapped[AddOn] = relationship()
    price_option: Mapped[PriceOption | None] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(pg_enum(PaymentStatus, "payment_status"), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship(back_populates="payments")
    creator: Mapped[User] = relationship(back_populates="payments")
