from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.models import (
    BusinessDay,
    BusinessDayStatus,
    DeliveryWorker,
    Order,
    OrderType,
    PaymentStatus,
    TelegramMessageType,
    TelegramOutbox,
    TelegramOutboxStatus,
    User,
    UserRole,
)
from app.services.business_day_service import (
    close_previous_business_day,
    get_current_business_date,
)
from app.services.errors import ServiceError

TASHKENT = ZoneInfo("Asia/Tashkent")


def _close_time(business_date: date) -> datetime:
    return datetime.combine(business_date + timedelta(days=1), time(6, 5), tzinfo=TASHKENT)


def _seed_report_data(session: Session, previous_date: date) -> dict[str, int]:
    suffix = uuid4().hex[:10]
    admin = User(
        name=f"Report Admin {suffix}",
        username=f"report-admin-{suffix}",
        password_hash="hash",
        role=UserRole.ADMIN,
        is_active=True,
    )
    ali = DeliveryWorker(name=f"Ali {suffix}", phone=f"report-ali-{suffix}", is_active=True)
    vali = DeliveryWorker(name=f"Vali {suffix}", phone=f"report-vali-{suffix}", is_active=True)
    previous_day = BusinessDay(
        business_date=previous_date,
        started_at=datetime.combine(previous_date, time(6), tzinfo=TASHKENT),
        status=BusinessDayStatus.OPEN,
    )
    session.add_all([admin, ali, vali, previous_day])
    session.flush()

    def add_order(
        number: str,
        order_type: OrderType,
        status: PaymentStatus,
        total_amount: int,
        worker_id: int | None = None,
    ) -> None:
        session.add(
            Order(
                order_number=f"r{suffix}-{number}",
                business_day_id=previous_day.id,
                order_type=order_type,
                delivery_worker_id=worker_id,
                created_by=admin.id,
                payment_status=status,
                total_amount=total_amount,
                cancelled_at=(
                    datetime.combine(previous_date, time(12), tzinfo=TASHKENT)
                    if status is PaymentStatus.CANCELLED
                    else None
                ),
                cancelled_by=admin.id if status is PaymentStatus.CANCELLED else None,
                cancel_reason="Test cancellation" if status is PaymentStatus.CANCELLED else None,
            )
        )

    # These are historical snapshots, deliberately not derived from catalog data.
    add_order("chay-paid-1", OrderType.CHAYKHANA, PaymentStatus.PAID, 20_000)
    add_order("chay-paid-2", OrderType.CHAYKHANA, PaymentStatus.PAID, 30_000)
    add_order("delivery-ali", OrderType.DELIVERY, PaymentStatus.PAID, 35_000, ali.id)
    add_order("delivery-vali", OrderType.DELIVERY, PaymentStatus.PAID, 14_000, vali.id)
    add_order("cancelled", OrderType.CHAYKHANA, PaymentStatus.CANCELLED, 12_000)
    add_order("pending", OrderType.DELIVERY, PaymentStatus.PENDING, 7_000, ali.id)
    session.flush()
    return {
        "admin_id": admin.id,
        "ali_id": ali.id,
        "vali_id": vali.id,
        "previous_day_id": previous_day.id,
    }


def test_business_day_boundary_is_06_tashkent() -> None:
    before = datetime(2040, 9, 9, 5, 59, 59, tzinfo=TASHKENT)
    at_boundary = datetime(2040, 9, 9, 6, 0, tzinfo=TASHKENT)

    assert get_current_business_date(before) == date(2040, 9, 8)
    assert get_current_business_date(at_boundary) == date(2040, 9, 9)


def test_close_previous_day_builds_paid_snapshot_report_and_is_idempotent(db: Session) -> None:
    previous_date = date(2070, 5, 10)
    ids = _seed_report_data(db, previous_date)
    now = _close_time(previous_date)

    result = close_previous_business_day(db, now)

    assert result.report_created is True
    assert result.previous_day is not None
    assert result.previous_day.status is BusinessDayStatus.CLOSED
    assert result.previous_day.closed_at == now
    assert result.current_day.business_date == previous_date + timedelta(days=1)
    assert result.current_day.status is BusinessDayStatus.OPEN
    assert result.report is not None
    assert result.report.chaykhana.count == 2
    assert result.report.chaykhana.amount == 50_000
    assert result.report.delivery.count == 2
    assert result.report.delivery.amount == 49_000
    assert [(worker.worker_name.split()[0], worker.count, worker.amount) for worker in result.report.delivery_workers] == [
        ("Ali", 1, 35_000),
        ("Vali", 1, 14_000),
    ]
    assert result.report.overall.count == 4
    assert result.report.overall.amount == 99_000
    assert result.report.cancelled.count == 1
    assert result.report.cancelled.amount == 12_000
    assert result.report.pending_count == 1

    outboxes = db.scalars(
        select(TelegramOutbox).where(
            TelegramOutbox.message_type == TelegramMessageType.DAILY_REPORT,
            TelegramOutbox.message_text.contains(previous_date.strftime("%d.%m.%Y")),
        )
    ).all()
    assert len(outboxes) == 1
    outbox = outboxes[0]
    assert outbox.order_id is None
    assert outbox.status is TelegramOutboxStatus.PENDING
    message = outbox.message_text
    assert "📊 KUNLIK HISOBOT" in message
    assert "📅 10.05.2070" in message
    assert "Choyxonada:\nBuyurtmalar: 2\nSumma: 50 000 so‘m" in message
    assert "Yetkazib berish:\nBuyurtmalar: 2\nSumma: 49 000 so‘m" in message
    assert message.count("Buyurtmalar: 2") == 2
    assert "Jami:\n4 ta buyurtma\n99 000 so‘m" in message
    assert "Bekor qilingan:\n1 ta / 12 000 so‘m" in message
    assert "Kutilayotgan:\n1 ta" in message
    for worker in result.report.delivery_workers:
        worker_line = f"{worker.worker_name} — {worker.count} ta / {worker.amount:,}".replace(",", " ") + " so‘m"
        assert worker_line in message

    pending = db.scalars(
        select(Order).where(
            Order.business_day_id == ids["previous_day_id"],
            Order.payment_status == PaymentStatus.PENDING,
        )
    ).one()
    assert pending.business_day_id == ids["previous_day_id"]

    second = close_previous_business_day(db, now)
    assert second.report_created is False
    assert second.previous_day is not None
    assert second.previous_day.id == ids["previous_day_id"]
    assert db.scalar(
        select(func.count()).select_from(TelegramOutbox).where(
            TelegramOutbox.message_type == TelegramMessageType.DAILY_REPORT,
            TelegramOutbox.message_text.contains(previous_date.strftime("%d.%m.%Y")),
        )
    ) == 1
    assert db.scalar(
        select(func.count()).select_from(BusinessDay).where(
            BusinessDay.business_date == previous_date + timedelta(days=1)
        )
    ) == 1


def test_close_previous_day_is_not_available_before_06(db: Session) -> None:
    with pytest.raises(ServiceError) as error:
        close_previous_business_day(db, datetime(2070, 5, 11, 5, 59, 59, tzinfo=TASHKENT))

    assert error.value.code == "business_day_close_not_available"


def test_concurrent_close_creates_one_report() -> None:
    previous_date = date(2080, 1, 1) + timedelta(days=int(uuid4().hex[:4], 16) % 5_000)
    seed = SessionLocal()
    try:
        ids = _seed_report_data(seed, previous_date)
        seed.commit()
    finally:
        seed.close()

    start = Barrier(2)

    def close_once() -> bool:
        session = SessionLocal()
        try:
            start.wait()
            result = close_previous_business_day(session, _close_time(previous_date))
            session.commit()
            return result.report_created
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: close_once(), range(2)))

    verifier = SessionLocal()
    try:
        previous_day = verifier.get(BusinessDay, ids["previous_day_id"])
        reports = verifier.scalars(
            select(TelegramOutbox).where(
                TelegramOutbox.message_type == TelegramMessageType.DAILY_REPORT,
                TelegramOutbox.message_text.contains(previous_date.strftime("%d.%m.%Y")),
            )
        ).all()
        assert outcomes.count(True) == 1
        assert outcomes.count(False) == 1
        assert previous_day is not None and previous_day.status is BusinessDayStatus.CLOSED
        assert len(reports) == 1
        report_ids = [report.id for report in reports]
        current_days = verifier.scalar(
            select(func.count()).select_from(BusinessDay).where(
                BusinessDay.business_date == previous_date + timedelta(days=1)
            )
        )
        assert current_days == 1
    finally:
        verifier.close()

    cleanup = SessionLocal()
    try:
        cleanup.execute(delete(TelegramOutbox).where(TelegramOutbox.id.in_(report_ids)))
        cleanup.execute(delete(Order).where(Order.business_day_id == ids["previous_day_id"]))
        cleanup.execute(
            delete(BusinessDay).where(
                BusinessDay.id.in_([ids["previous_day_id"]]),
            )
        )
        cleanup.execute(
            delete(BusinessDay).where(BusinessDay.business_date == previous_date + timedelta(days=1))
        )
        cleanup.execute(delete(User).where(User.id == ids["admin_id"]))
        cleanup.execute(delete(DeliveryWorker).where(DeliveryWorker.id.in_([ids["ali_id"], ids["vali_id"]])))
        cleanup.commit()
    finally:
        cleanup.close()
