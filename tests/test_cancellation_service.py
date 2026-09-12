from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal, get_db
from app.models import (
    BusinessDay, BusinessDayStatus, DeliveryWorker, Order, OrderType, Payment,
    PaymentStatus, PrintJob, TelegramMessageType, TelegramOutbox, User, UserRole,
)
from app.services.cancellation_service import cancel_order
from app.services.errors import ServiceError
from app.services.payment_service import pay_order
from main import app
from tests.auth_helpers import auth_headers

TASHKENT = ZoneInfo("Asia/Tashkent")


def _pending_order(db: Session, delivery: bool = False) -> Order:
    suffix = uuid4().hex[:10]
    business_date = date(2060, 1, 1) + timedelta(days=int(suffix[:4], 16) % 3000)
    admin = User(name="Administrator", username=f"cancel-admin-{suffix}", password_hash="hash", role=UserRole.ADMIN, is_active=True)
    worker = DeliveryWorker(name=f"Ali {suffix}", phone=f"cancel-{suffix}", is_active=True) if delivery else None
    day = BusinessDay(business_date=business_date, started_at=datetime.combine(business_date, datetime.min.time(), tzinfo=TASHKENT), status=BusinessDayStatus.OPEN)
    db.add_all([admin, day] + ([worker] if worker else []))
    db.flush()
    order = Order(
        order_number=f"c{suffix}", business_day_id=day.id,
        order_type=OrderType.DELIVERY if delivery else OrderType.CHAYKHANA,
        delivery_worker_id=worker.id if worker else None, created_by=admin.id,
        payment_status=PaymentStatus.PENDING, total_amount=30000,
    )
    db.add(order)
    db.flush()
    return order


def test_pending_order_cancellation_creates_outbox_without_payment_or_print(db: Session) -> None:
    order = _pending_order(db)
    result = cancel_order(db, order.id, "  Mijoz buyurtmani bekor qildi  ", order.created_by)
    outbox = db.scalars(select(TelegramOutbox).where(TelegramOutbox.order_id == order.id)).one()

    assert result.order.payment_status is PaymentStatus.CANCELLED
    assert result.order.cancelled_at is not None
    assert result.order.canceller.name == "Administrator"
    assert result.order.cancel_reason == "Mijoz buyurtmani bekor qildi"
    assert outbox.message_type is TelegramMessageType.CANCELLED_ORDER
    assert outbox.status.value == "PENDING"
    assert f"#{order.order_number}" in outbox.message_text
    assert "30 000 so‘m" in outbox.message_text
    assert "Mijoz buyurtmani bekor qildi" in outbox.message_text
    assert "Yetkazib beruvchi" not in outbox.message_text
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order.id)) == 0
    assert db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.order_id == order.id)) == 0


def test_delivery_cancellation_is_idempotent_and_paid_order_is_rejected(db: Session) -> None:
    delivery = _pending_order(db, delivery=True)
    cancel_order(db, delivery.id, "Mijoz rad etdi", delivery.created_by)
    message = db.scalars(select(TelegramOutbox.message_text).where(TelegramOutbox.order_id == delivery.id)).one()
    assert "Yetkazib beruvchi: Ali" in message
    with pytest.raises(ServiceError) as repeated:
        cancel_order(db, delivery.id, "Ikkinchi urinish", delivery.created_by)
    assert repeated.value.code == "ORDER_ALREADY_CANCELLED"

    paid = _pending_order(db)
    paid.payment_status = PaymentStatus.PAID
    with pytest.raises(ServiceError) as paid_error:
        cancel_order(db, paid.id, "Refund so‘rovi", paid.created_by)
    assert paid_error.value.code == "PAID_ORDER_CANNOT_BE_CANCELLED"


@pytest.mark.parametrize("reason", ["", "   "])
def test_cancellation_requires_non_blank_reason(db: Session, reason: str) -> None:
    order = _pending_order(db)
    with pytest.raises(ServiceError) as error:
        cancel_order(db, order.id, reason, order.created_by)
    assert error.value.code == "CANCEL_REASON_REQUIRED"


def test_cancel_api_and_order_detail_expose_cancellation_metadata(db: Session) -> None:
    order = _pending_order(db)
    order_id = order.id
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=auth_headers(db.get(User, order.created_by))) as client:
            response = client.post(f"/api/orders/{order_id}/cancel", json={"reason": "Mijoz ketdi"})
            assert response.status_code == 200, response.text
            assert response.json()["payment_status"] == "CANCELLED"
            assert response.json()["cancelled_by"]["name"] == "Administrator"
            assert response.json()["cancel_reason"] == "Mijoz ketdi"
            detail = client.get(f"/api/orders/{order_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["payment_status"] == "CANCELLED"
            assert detail.json()["cancel_reason"] == "Mijoz ketdi"
            assert detail.json()["cancelled_at"] is not None
            assert detail.json()["cancelled_by"]["name"] == "Administrator"
            second = client.post(f"/api/orders/{order_id}/cancel", json={"reason": "again"})
            assert second.status_code == 409, second.text
            assert second.json()["error"]["code"] == "ORDER_ALREADY_CANCELLED"
    finally:
        app.dependency_overrides.clear()


def test_concurrent_payment_and_cancellation_leave_one_valid_outcome() -> None:
    seed = SessionLocal()
    try:
        order = _pending_order(seed)
        order_id, day_id, admin_id = order.id, order.business_day_id, order.created_by
        seed.commit()
    finally:
        seed.close()
    start = Barrier(2)

    def pay() -> str:
        session = SessionLocal()
        try:
            start.wait()
            pay_order(session, order_id, admin_id)
            session.commit()
            return "PAID"
        except ServiceError as error:
            session.rollback()
            return error.code
        finally:
            session.close()

    def cancel() -> str:
        session = SessionLocal()
        try:
            start.wait()
            cancel_order(session, order_id, "Parallel cancel", admin_id)
            session.commit()
            return "CANCELLED"
        except ServiceError as error:
            session.rollback()
            return error.code
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        payment_attempt = executor.submit(pay)
        cancellation_attempt = executor.submit(cancel)
        outcomes = [payment_attempt.result(), cancellation_attempt.result()]

    verify = SessionLocal()
    try:
        final = verify.get(Order, order_id)
        assert outcomes.count("PAID") + outcomes.count("CANCELLED") == 1
        assert final.payment_status in (PaymentStatus.PAID, PaymentStatus.CANCELLED)
        payments = verify.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order_id))
        paid_outbox = verify.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order_id, TelegramOutbox.message_type == TelegramMessageType.PAID_ORDER))
        cancelled_outbox = verify.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order_id, TelegramOutbox.message_type == TelegramMessageType.CANCELLED_ORDER))
        if final.payment_status is PaymentStatus.PAID:
            assert payments == paid_outbox == 1 and cancelled_outbox == 0
        else:
            assert payments == paid_outbox == 0 and cancelled_outbox == 1
    finally:
        verify.close()

    cleanup = SessionLocal()
    try:
        cleanup.execute(delete(TelegramOutbox).where(TelegramOutbox.order_id == order_id))
        cleanup.execute(delete(Payment).where(Payment.order_id == order_id))
        cleanup.execute(delete(Order).where(Order.id == order_id))
        cleanup.execute(delete(BusinessDay).where(BusinessDay.id == day_id))
        cleanup.execute(delete(User).where(User.id == admin_id))
        cleanup.commit()
    finally:
        cleanup.close()
