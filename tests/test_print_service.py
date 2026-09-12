from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.printing import get_printer_adapter
from app.database.connection import get_db
from app.models import (
    AddOn, BusinessDay, BusinessDayStatus, Category, Order, OrderItem, OrderItemAddOn,
    OrderType, Payment, PaymentStatus, PrintJob, PrintJobStatus, Printer, PrinterConnectionType,
    Product, ProductAddOn, Setting, TelegramMessageType, TelegramOutbox, TelegramOutboxStatus,
    UnitType, User, UserRole,
)
from app.printer.interface import PrinterError
from app.services.errors import ServiceError
from app.services.print_service import print_order, retry_print_job
from main import app
from tests.auth_helpers import auth_headers

TASHKENT = ZoneInfo("Asia/Tashkent")


class FakePrinter:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.receipts: list[str] = []

    def print_receipt(self, _printer: Printer, receipt: str) -> None:
        if self.error:
            raise PrinterError(self.error)
        self.receipts.append(receipt)


def _paid_order_with_printer(db: Session, delivery: bool = False) -> tuple[Order, Printer]:
    suffix = uuid4().hex[:10]
    admin = User(name="Print Admin", username=f"print-admin-{suffix}", password_hash="hash", role=UserRole.ADMIN, is_active=True)
    day = BusinessDay(business_date=date(2050, 1, 1), started_at=datetime(2050, 1, 1, 6, tzinfo=TASHKENT), status=BusinessDayStatus.OPEN)
    category = Category(name=f"Print category {suffix}", sort_order=1, is_active=True)
    worker = None
    if delivery:
        from app.models import DeliveryWorker
        worker = DeliveryWorker(name=f"Ali {suffix}", phone=f"print-{suffix}", is_active=True)
    osh = Product(category=category, name=f"Osh {suffix}", unit_type=UnitType.PORTION, base_price=0, allows_manual_price=False, is_active=True)
    gosht = AddOn(name=f"Go'sht {suffix}", unit_type=UnitType.AMOUNT, base_price=0, allows_manual_price=True, is_active=True)
    printer = Printer(name=f"Printer {suffix}", terminal_name="POS1", connection_type=PrinterConnectionType.NETWORK, address="127.0.0.1:9100", is_active=True)
    db.add_all([admin, day, category, osh, gosht, printer, Setting(key=f"unused-{suffix}", value="x")] + ([worker] if worker else []))
    db.flush()
    setting = db.scalars(select(Setting).where(Setting.key == "restaurant_name")).one_or_none()
    if setting is None:
        db.add(Setting(key="restaurant_name", value="Test Restaurant"))
    db.add(ProductAddOn(product_id=osh.id, addon_id=gosht.id, is_required=False, is_active=True))
    order = Order(
        order_number=f"p{suffix}", business_day_id=day.id,
        order_type=OrderType.DELIVERY if delivery else OrderType.CHAYKHANA,
        delivery_worker_id=worker.id if worker else None, created_by=admin.id,
        payment_status=PaymentStatus.PAID, paid_at=datetime.now(TASHKENT), total_amount=30000,
    )
    db.add(order)
    db.flush()
    item = OrderItem(order_id=order.id, product_id=osh.id, quantity=Decimal("1.000"), unit_price=15000, total_price=30000, selected_price_option_id=None, manual_price=None)
    db.add(item)
    db.flush()
    db.add_all([
        OrderItemAddOn(order_item_id=item.id, addon_id=gosht.id, quantity=Decimal("1.000"), unit_price=15000, total_price=15000, price_option_id=None, manual_price=15000),
        Payment(order_id=order.id, amount=30000, status=PaymentStatus.PAID, paid_at=order.paid_at, created_by=admin.id),
        TelegramOutbox(message_type=TelegramMessageType.PAID_ORDER, order_id=order.id, message_text="paid", status=TelegramOutboxStatus.PENDING, attempts=0),
    ])
    db.flush()
    return order, printer


def test_successful_print_builds_receipt_and_preserves_payment(db: Session) -> None:
    order, printer = _paid_order_with_printer(db)
    adapter = FakePrinter()

    result = print_order(db, order.id, printer.id, adapter)

    assert result.job.status is PrintJobStatus.SUCCESS
    assert result.job.printed_at is not None
    assert len(adapter.receipts) == 1
    receipt = adapter.receipts[0]
    assert f"#{order.order_number}" in receipt
    assert "Osh" in receipt and "Go'sht" in receipt and "15 000 so‘m" in receipt
    assert "Yetkazib beruvchi:" not in receipt
    assert db.get(Order, order.id).payment_status is PaymentStatus.PAID
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order.id)) == 1
    assert db.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order.id)) == 1


def test_printer_error_is_recorded_and_retry_preserves_history(db: Session) -> None:
    order, printer = _paid_order_with_printer(db)
    failing = FakePrinter("Printer offline")
    failed = print_order(db, order.id, printer.id, failing)
    assert failed.job.status is PrintJobStatus.ERROR
    assert failed.job.error_message == "Printer offline"
    assert db.get(Order, order.id).payment_status is PaymentStatus.PAID
    assert db.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order.id)) == 1
    assert db.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order.id)) == 1

    retried = retry_print_job(db, failed.job.id, FakePrinter())
    assert retried.job.id != failed.job.id
    assert retried.job.status is PrintJobStatus.SUCCESS
    assert db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.order_id == order.id)) == 2


def test_delivery_receipt_and_printer_validation(db: Session) -> None:
    order, printer = _paid_order_with_printer(db, delivery=True)
    adapter = FakePrinter()
    print_order(db, order.id, printer.id, adapter)
    assert "Yetkazib beruvchi: Ali" in adapter.receipts[0]
    printer.is_active = False
    with pytest.raises(ServiceError) as inactive:
        print_order(db, order.id, printer.id, adapter)
    assert inactive.value.code == "PRINTER_INACTIVE"
    with pytest.raises(ServiceError) as missing:
        print_order(db, 999_999_999, printer.id, adapter)
    assert missing.value.code == "ORDER_NOT_FOUND"
    with pytest.raises(ServiceError) as missing_printer:
        print_order(db, order.id, 999_999_999, adapter)
    assert missing_printer.value.code == "PRINTER_NOT_FOUND"


def test_print_api_uses_injected_fake_adapter(db: Session) -> None:
    order, printer = _paid_order_with_printer(db)
    fake = FakePrinter()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_printer_adapter] = lambda: fake
    try:
        with TestClient(app, headers=auth_headers(db.get(User, order.created_by))) as client:
            response = client.post(f"/api/orders/{order.id}/print", json={"printer_id": printer.id})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "SUCCESS"
        assert response.json()["printed_at"] is not None
    finally:
        app.dependency_overrides.clear()
