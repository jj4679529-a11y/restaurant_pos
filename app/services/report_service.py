from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BusinessDay, DeliveryWorker, Order, OrderType, PaymentStatus, Payment, User


@dataclass(frozen=True)
class OrderTotals:
    count: int
    amount: int


@dataclass(frozen=True)
class DeliveryWorkerReport:
    worker_id: int
    worker_name: str
    count: int
    amount: int


@dataclass(frozen=True)
class DailyReportData:
    business_date: date
    chaykhana: OrderTotals
    delivery: OrderTotals
    delivery_workers: tuple[DeliveryWorkerReport, ...]
    overall: OrderTotals
    cancelled: OrderTotals
    pending_count: int
    cashiers: tuple[tuple[str, int], ...] = ()


def _totals(session: Session, business_day_id: int, status: PaymentStatus, order_type: OrderType | None = None) -> OrderTotals:
    query = select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(
        Order.business_day_id == business_day_id,
        Order.payment_status == status,
    )
    if order_type is not None:
        query = query.where(Order.order_type == order_type)
    count, amount = session.execute(query).one()
    return OrderTotals(count=int(count), amount=int(amount))


def build_daily_report_data(session: Session, business_day: BusinessDay) -> DailyReportData:
    chaykhana = _totals(session, business_day.id, PaymentStatus.PAID, OrderType.CHAYKHANA)
    delivery = _totals(session, business_day.id, PaymentStatus.PAID, OrderType.DELIVERY)
    cancelled = _totals(session, business_day.id, PaymentStatus.CANCELLED)
    pending = _totals(session, business_day.id, PaymentStatus.PENDING)
    worker_rows = session.execute(
        select(
            DeliveryWorker.id,
            DeliveryWorker.name,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
        )
        .join(Order, Order.delivery_worker_id == DeliveryWorker.id)
        .where(
            Order.business_day_id == business_day.id,
            Order.order_type == OrderType.DELIVERY,
            Order.payment_status == PaymentStatus.PAID,
        )
        .group_by(DeliveryWorker.id, DeliveryWorker.name)
        .order_by(DeliveryWorker.name, DeliveryWorker.id)
    ).all()
    workers = tuple(
        DeliveryWorkerReport(worker_id=row.id, worker_name=row.name, count=int(row[2]), amount=int(row[3]))
        for row in worker_rows
    )
    return DailyReportData(
        business_date=business_day.business_date,
        chaykhana=chaykhana,
        delivery=delivery,
        delivery_workers=workers,
        overall=OrderTotals(count=chaykhana.count + delivery.count, amount=chaykhana.amount + delivery.amount),
        cancelled=cancelled,
        pending_count=pending.count,
        cashiers=tuple((name, int(amount)) for name, amount in session.execute(
            select(User.name, func.sum(Payment.amount))
            .join(Payment, Payment.created_by == User.id)
            .join(Order, Order.id == Payment.order_id)
            .where(Order.business_day_id == business_day.id,
                   Order.payment_status == PaymentStatus.PAID, Payment.status == PaymentStatus.PAID)
            .group_by(User.id, User.name).order_by(User.name, User.id)
        )),
    )
