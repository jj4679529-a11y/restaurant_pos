from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import engine
from app.models import (
    AddOn,
    BusinessDay,
    BusinessDayStatus,
    Category,
    DeliveryWorker,
    Order,
    OrderItem,
    OrderItemAddOn,
    OrderType,
    Payment,
    PaymentStatus,
    PriceOption,
    PrintJob,
    PrintJobStatus,
    Printer,
    PrinterConnectionType,
    Product,
    ProductAddOn,
    TelegramMessageType,
    TelegramOutbox,
    TelegramOutboxStatus,
    UnitType,
    User,
    UserRole,
)

TASHKENT = ZoneInfo("Asia/Tashkent")
EXPECTED_TABLES = {
    "manual_price_presets",
    "users",
    "categories",
    "products",
    "price_options",
    "add_ons",
    "product_addons",
    "delivery_workers",
    "business_days",
    "orders",
    "order_items",
    "order_item_addons",
    "payments",
    "printers",
    "print_jobs",
    "telegram_outbox",
    "settings",
}


def test_expected_tables_exist() -> None:
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def _user(db: Session) -> User:
    user = User(
        name="Cashier",
        username="cashier_test",
        password_hash="hashed-password-not-plain",
        role=UserRole.CASHIER,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _category(db: Session) -> Category:
    category = Category(name="Osh", sort_order=1, is_active=True)
    db.add(category)
    db.flush()
    return category


def _product(db: Session, category: Category) -> Product:
    product = Product(
        category_id=category.id,
        name="Osh",
        unit_type=UnitType.PORTION,
        base_price=25000,
        allows_manual_price=False,
        is_active=True,
    )
    db.add(product)
    db.flush()
    return product


def _business_day(db: Session, business_date: date | None = None) -> BusinessDay:
    day_date = business_date or date(2026, 9, 8)
    started_at = datetime(day_date.year, day_date.month, day_date.day, 6, 0, tzinfo=TASHKENT)
    closed_at = started_at + timedelta(hours=23, minutes=59, seconds=59)
    business_day = BusinessDay(
        business_date=day_date,
        started_at=started_at,
        closed_at=closed_at,
        status=BusinessDayStatus.OPEN,
    )
    db.add(business_day)
    db.flush()
    return business_day


def test_create_category(db: Session) -> None:
    category = _category(db)
    assert category.id is not None
    assert category.name == "Osh"


def test_create_product_with_category(db: Session) -> None:
    category = _category(db)
    product = _product(db, category)

    db.refresh(product)
    assert product.category_id == category.id
    assert product.category.name == "Osh"
    assert product.base_price == 25000
    assert isinstance(product.base_price, int)


def test_create_delivery_worker(db: Session) -> None:
    worker = DeliveryWorker(name="Ali", phone="+998901234567", is_active=True)
    db.add(worker)
    db.flush()
    assert worker.id is not None


def test_create_business_day(db: Session) -> None:
    business_day = _business_day(db)
    assert business_day.business_date == date(2026, 9, 8)
    assert business_day.started_at.tzinfo is not None
    assert business_day.status is BusinessDayStatus.OPEN


def test_business_date_is_unique(db: Session) -> None:
    _business_day(db)
    db.add(
        BusinessDay(
            business_date=date(2026, 9, 8),
            started_at=datetime(2026, 9, 8, 6, 0, tzinfo=TASHKENT),
            status=BusinessDayStatus.OPEN,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_create_order_item_payment(db: Session) -> None:
    user = _user(db)
    category = _category(db)
    product = _product(db, category)
    option = PriceOption(
        product_id=product.id,
        name="25000",
        quantity=Decimal("1.000"),
        price=25000,
        is_active=True,
    )
    db.add(option)
    business_day = _business_day(db)
    db.flush()

    order = Order(
        order_number="00125",
        business_day_id=business_day.id,
        order_type=OrderType.CHAYKHANA,
        delivery_worker_id=None,
        created_by=user.id,
        payment_status=PaymentStatus.PENDING,
        total_amount=25000,
    )
    db.add(order)
    db.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=Decimal("0.500"),
        unit_price=25000,
        total_price=12500,
        selected_price_option_id=option.id,
        manual_price=None,
    )
    db.add(item)
    db.flush()

    payment = Payment(
        order_id=order.id,
        amount=12500,
        status=PaymentStatus.PAID,
        paid_at=datetime.now(tz=TASHKENT),
        created_by=user.id,
    )
    db.add(payment)
    db.flush()

    assert order.items[0].quantity == Decimal("0.500")
    assert order.payments[0].amount == 12500
    assert item.unit_price == 25000


def test_order_requires_existing_business_day(db: Session) -> None:
    user = _user(db)
    db.add(
        Order(
            order_number="00126",
            business_day_id=999_999,
            order_type=OrderType.CHAYKHANA,
            created_by=user.id,
            payment_status=PaymentStatus.PENDING,
            total_amount=0,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_delivery_order_requires_worker(db: Session) -> None:
    user = _user(db)
    business_day = _business_day(db)
    db.add(
        Order(
            order_number="00127",
            business_day_id=business_day.id,
            order_type=OrderType.DELIVERY,
            delivery_worker_id=None,
            created_by=user.id,
            payment_status=PaymentStatus.PENDING,
            total_amount=0,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_create_printer_and_telegram_outbox(db: Session) -> None:
    user = _user(db)
    business_day = _business_day(db)
    order = Order(
        order_number="00128",
        business_day_id=business_day.id,
        order_type=OrderType.CHAYKHANA,
        created_by=user.id,
        payment_status=PaymentStatus.PAID,
        total_amount=10000,
    )
    printer = Printer(
        name="POS-1 kitchen",
        terminal_name="POS-1",
        connection_type=PrinterConnectionType.USB,
        address="/dev/usb/lp0",
        is_active=True,
    )
    db.add_all([order, printer])
    db.flush()

    print_job = PrintJob(
        order_id=order.id,
        printer_id=printer.id,
        status=PrintJobStatus.ERROR,
        error_message="printer offline",
    )
    outbox = TelegramOutbox(
        message_type=TelegramMessageType.PAID_ORDER,
        order_id=order.id,
        message_text="Order 00128 paid",
        status=TelegramOutboxStatus.PENDING,
        attempts=0,
    )
    db.add_all([print_job, outbox])
    db.flush()

    db.refresh(order)
    assert print_job.status is PrintJobStatus.ERROR
    assert order.payment_status is PaymentStatus.PAID
    assert outbox.status is TelegramOutboxStatus.PENDING


def test_product_addon_unique_pair(db: Session) -> None:
    category = _category(db)
    product = _product(db, category)
    addon = AddOn(
        name="Tuxum",
        unit_type=UnitType.PIECE,
        base_price=3000,
        allows_manual_price=False,
        is_active=True,
    )
    db.add(addon)
    db.flush()
    db.add(ProductAddOn(product_id=product.id, addon_id=addon.id, is_required=False, is_active=True))
    db.flush()
    db.add(ProductAddOn(product_id=product.id, addon_id=addon.id, is_required=True, is_active=True))
    with pytest.raises(IntegrityError):
        db.flush()


def test_order_item_addon_snapshot(db: Session) -> None:
    user = _user(db)
    category = _category(db)
    product = _product(db, category)
    addon = AddOn(
        name="Qazi",
        unit_type=UnitType.PIECE,
        base_price=8000,
        allows_manual_price=False,
        is_active=True,
    )
    business_day = _business_day(db)
    db.add(addon)
    db.flush()
    order = Order(
        order_number="00129",
        business_day_id=business_day.id,
        order_type=OrderType.CHAYKHANA,
        created_by=user.id,
        payment_status=PaymentStatus.PENDING,
        total_amount=33000,
    )
    db.add(order)
    db.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=Decimal("1.000"),
        unit_price=25000,
        total_price=25000,
    )
    db.add(item)
    db.flush()
    item_addon = OrderItemAddOn(
        order_item_id=item.id,
        addon_id=addon.id,
        quantity=Decimal("1.000"),
        unit_price=8000,
        total_price=8000,
    )
    db.add(item_addon)
    db.flush()
    assert item_addon.unit_price == 8000
    assert item.addons[0].addon_id == addon.id
