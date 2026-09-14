from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Order, Payment, PaymentStatus, TelegramMessageType, TelegramOutbox,
    TelegramOutboxStatus, User,
)
from app.services.errors import ServiceError
from app.telegram.message_builder import build_paid_order_message

TASHKENT = ZoneInfo("Asia/Tashkent")


@dataclass(frozen=True)
class PaymentResult:
    order: Order
    payment: Payment


def _actor(session: Session, actor_id: int) -> User:
    actor = session.get(User, actor_id)
    if actor is None or not actor.is_active:
        raise ServiceError(409, "PAYMENT_ACTOR_NOT_AVAILABLE", "Payment actor is not active")
    return actor


def _locked_order(session: Session, order_id: int) -> Order:
    order = session.scalars(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.delivery_worker))
        .with_for_update()
    ).one_or_none()
    if order is None:
        raise ServiceError(404, "ORDER_NOT_FOUND", "Order not found")
    return order


def pay_order(session: Session, order_id: int, actor_id: int) -> PaymentResult:
    """Apply payment state within the transaction owned by the caller."""
    order = _locked_order(session, order_id)
    if order.payment_status is PaymentStatus.PAID:
        raise ServiceError(409, "ORDER_ALREADY_PAID", "Order is already paid")
    if order.payment_status is PaymentStatus.CANCELLED:
        raise ServiceError(409, "ORDER_CANCELLED", "Cancelled orders cannot be paid")
    if order.payment_status is not PaymentStatus.PENDING:
        raise ServiceError(409, "ORDER_NOT_PAYABLE", "Order cannot be paid in its current state")

    paid_at = datetime.now(TASHKENT)
    actor = _actor(session, actor_id)
    payment = Payment(
        order_id=order.id,
        amount=order.total_amount,
        status=PaymentStatus.PAID,
        paid_at=paid_at,
        created_by=actor.id,
    )
    order.payment_status = PaymentStatus.PAID
    order.paid_at = paid_at
    session.add(payment)
    session.flush()
    session.add(TelegramOutbox(
        message_type=TelegramMessageType.PAID_ORDER,
        order_id=order.id,
        message_text=build_paid_order_message(order, actor.name),
        status=TelegramOutboxStatus.PENDING,
        attempts=0,
    ))
    return PaymentResult(order=order, payment=payment)
