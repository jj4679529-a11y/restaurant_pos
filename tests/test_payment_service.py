from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
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
    PaymentStatus, TelegramMessageType, TelegramOutbox, User, UserRole,
)
from app.services.errors import ServiceError
from app.services.payment_service import pay_order
from main import app
from tests.auth_helpers import auth_headers

TASHKENT = ZoneInfo("Asia/Tashkent")


def _pending_order(db: Session, delivery: bool = False) -> Order:
    suffix = uuid4().hex[:10]
    business_date = date(2045, 1, 1) + timedelta(days=int(suffix[:4], 16) % 7000)
    admin = User(name="Payment Admin", username=f"payment-admin-{suffix}", password_hash="hash", role=UserRole.ADMIN, is_active=True)
    worker = DeliveryWorker(name=f"Delivery {suffix}", phone=f"payment-{suffix}", is_active=True) if delivery else None
    day = BusinessDay(
        business_date=business_date,
        started_at=datetime.combine(business_date, datetime.min.time(), tzinfo=TASHKENT),
        status=BusinessDayStatus.OPEN,
    )
    db.add_all([admin, day] + ([worker] if worker else []))
    db.flush()
    order = Order(
        order_number=f"p{suffix}",
        business_day_id=day.id,
        order_type=OrderType.DELIVERY if delivery else OrderType.CHAYKHANA,
        delivery_worker_id=worker.id if worker else None,
        created_by=admin.id,
        payment_status=PaymentStatus.PENDING,
        total_amount=73000,
    )
    db.add(order)
    db.flush()
    return order


def test_pay_pending_order_creates_payment_and_outbox(db: Session) -> None:
    order = _pending_order(db)

    result = pay_order(db, order.id, order.created_by)

    refreshed = db.get(Order, order.id)
    payments = db.scalars(select(Payment).where(Payment.order_id == order.id)).all()
    outbox = db.scalars(select(TelegramOutbox).where(TelegramOutbox.order_id == order.id)).all()
    assert result.payment.amount == 73000
    assert refreshed.payment_status is PaymentStatus.PAID
    assert refreshed.paid_at is not None
    assert len(payments) == 1 and payments[0].status is PaymentStatus.PAID
    assert len(outbox) == 1
    assert outbox[0].message_type is TelegramMessageType.PAID_ORDER
    assert "#" + order.order_number in outbox[0].message_text
    assert "73 000 so‘m" in outbox[0].message_text
    assert "Vaqt:" in outbox[0].message_text
    assert "Yetkazib beruvchi" not in outbox[0].message_text


def test_delivery_payment_message_includes_worker_and_repeated_pay_is_conflict(db: Session) -> None:
    order = _pending_order(db, delivery=True)
    pay_order(db, order.id, order.created_by)

    message = db.scalars(select(TelegramOutbox.message_text).where(TelegramOutbox.order_id == order.id)).one()
    assert "Yetkazib beruvchi: Delivery" in message
    with pytest.raises(ServiceError) as error:
        pay_order(db, order.id, order.created_by)
    assert error.value.status_code == 409
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order.id)) == 1
    assert db.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order.id)) == 1


def test_cancelled_and_missing_orders_cannot_be_paid(db: Session) -> None:
    order = _pending_order(db)
    order.payment_status = PaymentStatus.CANCELLED
    db.commit()
    with pytest.raises(ServiceError) as cancelled:
        pay_order(db, order.id, order.created_by)
    assert cancelled.value.code == "ORDER_CANCELLED"
    with pytest.raises(ServiceError) as missing:
        pay_order(db, 999_999_999, order.created_by)
    assert missing.value.code == "ORDER_NOT_FOUND"


def test_pay_api_response_and_idempotency(db: Session) -> None:
    order = _pending_order(db)
    order_id = order.id
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=auth_headers(db.get(User, order.created_by))) as client:
            paid = client.post(f"/api/orders/{order_id}/pay")
            assert paid.status_code == 200, paid.text
            assert paid.json()["order_id"] == order_id
            assert paid.json()["payment_status"] == "PAID"
            assert paid.json()["amount"] == 73000
            assert paid.json()["paid_at"] is not None
            assert paid.json()["payment_id"] > 0
            again = client.post(f"/api/orders/{order_id}/pay")
            assert again.status_code == 409
            assert again.json()["error"]["code"] == "ORDER_ALREADY_PAID"
    finally:
        app.dependency_overrides.clear()


def test_pay_api_missing_order_is_not_found(db: Session) -> None:
    order = _pending_order(db)
    actor = db.get(User, order.created_by)
    assert actor is not None
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=auth_headers(actor)) as client:
            missing = client.post("/api/orders/999999999/pay")
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "ORDER_NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_concurrent_payment_creates_one_payment_and_one_outbox(db: Session) -> None:
    seed_session = SessionLocal()
    try:
        order = _pending_order(seed_session)
        order_id = order.id
        business_day_id = order.business_day_id
        admin_id = order.created_by
        worker_id = order.delivery_worker_id
        seed_session.commit()
    finally:
        seed_session.close()
    start = Barrier(2)

    def attempt_payment() -> str:
        session = SessionLocal()
        try:
            start.wait()
            result = pay_order(session, order_id, admin_id)
            session.commit()
            return "PAID"
        except ServiceError as error:
            session.rollback()
            return error.code
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _index: attempt_payment(), range(2)))

    verifier = SessionLocal()
    try:
        verified_order = verifier.get(Order, order_id)
        assert outcomes.count("PAID") == 1
        assert outcomes.count("ORDER_ALREADY_PAID") == 1
        assert verified_order is not None and verified_order.payment_status is PaymentStatus.PAID
        assert verifier.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order_id)) == 1
        assert verifier.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order_id)) == 1
    finally:
        verifier.close()

    cleanup = SessionLocal()
    try:
        cleanup.execute(delete(TelegramOutbox).where(TelegramOutbox.order_id == order_id))
        cleanup.execute(delete(Payment).where(Payment.order_id == order_id))
        cleanup.execute(delete(Order).where(Order.id == order_id))
        cleanup.execute(delete(BusinessDay).where(BusinessDay.id == business_day_id))
        cleanup.execute(delete(User).where(User.id == admin_id))
        if worker_id is not None:
            cleanup.execute(delete(DeliveryWorker).where(DeliveryWorker.id == worker_id))
        cleanup.commit()
    finally:
        cleanup.close()
