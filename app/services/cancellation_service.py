from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Order, PaymentStatus, TelegramMessageType, TelegramOutbox, TelegramOutboxStatus, User,
)
from app.services.errors import ServiceError
from app.telegram.message_builder import build_cancelled_order_message

TASHKENT = ZoneInfo("Asia/Tashkent")


@dataclass(frozen=True)
class CancellationResult:
    order: Order


def _locked_order(session: Session, order_id: int) -> Order:
    order = session.scalars(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.delivery_worker), selectinload(Order.canceller))
        .with_for_update()
    ).one_or_none()
    if order is None:
        raise ServiceError(404, "ORDER_NOT_FOUND", "Order not found")
    return order


def _actor(session: Session, actor_id: int) -> User:
    actor = session.get(User, actor_id)
    if actor is None or not actor.is_active:
        raise ServiceError(409, "CANCELLATION_ACTOR_NOT_AVAILABLE", "Cancellation actor is not active")
    return actor


def cancel_order(
    session: Session,
    order_id: int,
    reason: str,
    actor_id: int,
) -> CancellationResult:
    """Cancel a pending order inside the transaction owned by the caller."""
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ServiceError(422, "CANCEL_REASON_REQUIRED", "Cancellation reason is required")

    order = _locked_order(session, order_id)
    if order.payment_status is PaymentStatus.PAID:
        raise ServiceError(409, "PAID_ORDER_CANNOT_BE_CANCELLED", "Paid orders cannot be cancelled")
    if order.payment_status is PaymentStatus.CANCELLED:
        raise ServiceError(409, "ORDER_ALREADY_CANCELLED", "Order is already cancelled")
    if order.payment_status is not PaymentStatus.PENDING:
        raise ServiceError(409, "ORDER_NOT_CANCELLABLE", "Order cannot be cancelled in its current state")

    actor = _actor(session, actor_id)
    order.payment_status = PaymentStatus.CANCELLED
    order.cancelled_at = datetime.now(TASHKENT)
    order.canceller = actor
    order.cancel_reason = normalized_reason
    session.add(TelegramOutbox(
        message_type=TelegramMessageType.CANCELLED_ORDER,
        order_id=order.id,
        message_text=build_cancelled_order_message(order),
        status=TelegramOutboxStatus.PENDING,
        attempts=0,
    ))
    return CancellationResult(order=order)
