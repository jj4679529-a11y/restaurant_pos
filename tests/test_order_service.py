from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AddOn, BusinessDay, Category, DeliveryWorker, Order, OrderType, PriceOption,
    Product, ProductAddOn, UnitType, User, UserRole,
)
from app.schemas.orders import OrderCreate
from app.services import business_day_service, order_service
from app.services.errors import ServiceError

TASHKENT = ZoneInfo("Asia/Tashkent")


def _catalog(db: Session):
    suffix = uuid4().hex[:8]
    category = Category(name=f"Orders {suffix}", sort_order=1, is_active=True)
    admin = User(name="Order Admin", username=f"order-admin-{suffix}", password_hash="hash", role=UserRole.ADMIN, is_active=True)
    osh = Product(category=category, name=f"Osh {suffix}", unit_type=UnitType.PORTION, base_price=0, allows_manual_price=False, is_active=True)
    other = Product(category=category, name=f"Other {suffix}", unit_type=UnitType.PIECE, base_price=12000, allows_manual_price=False, is_active=True)
    unpriced = Product(category=category, name=f"Unpriced {suffix}", unit_type=UnitType.PIECE, base_price=0, allows_manual_price=False, is_active=True)
    option = PriceOption(product=osh, name="30000", quantity=Decimal("1"), price=30000, is_active=True)
    inactive_option = PriceOption(product=osh, name="15000", quantity=Decimal("1"), price=15000, is_active=False)
    egg = AddOn(name=f"Egg {suffix}", unit_type=UnitType.PIECE, base_price=2000, allows_manual_price=False, is_active=True)
    meat = AddOn(name=f"Go'sht {suffix}", unit_type=UnitType.AMOUNT, base_price=0, allows_manual_price=True, is_active=True)
    inactive = AddOn(name=f"Inactive {suffix}", unit_type=UnitType.PIECE, base_price=1000, allows_manual_price=False, is_active=False)
    worker = DeliveryWorker(name=f"Worker {suffix}", phone=f"order-{suffix}", is_active=True)
    db.add_all([category, admin, osh, other, unpriced, option, inactive_option, egg, meat, inactive, worker])
    db.flush()
    db.add_all([
        ProductAddOn(product_id=osh.id, addon_id=egg.id, is_required=False, is_active=True),
        ProductAddOn(product_id=osh.id, addon_id=meat.id, is_required=False, is_active=True),
        ProductAddOn(product_id=osh.id, addon_id=inactive.id, is_required=False, is_active=True),
    ])
    db.commit()
    return osh, other, unpriced, option, inactive_option, egg, meat, inactive, worker, admin


def _order(product_id: int, option_id: int | None, addons: list[dict] | None = None, **kwargs) -> OrderCreate:
    return OrderCreate.model_validate({
        "order_type": "CHAYKHANA",
        "items": [{"product_id": product_id, "quantity": "1", "selected_price_option_id": option_id, "addons": addons or []}],
        **kwargs,
    })


def test_business_day_boundary_and_get_or_create(db: Session) -> None:
    before = datetime(2040, 9, 9, 5, 59, 59, tzinfo=TASHKENT)
    after = datetime(2040, 9, 9, 6, 0, tzinfo=TASHKENT)
    assert business_day_service.get_current_business_date(before).isoformat() == "2040-09-08"
    assert business_day_service.get_current_business_date(after).isoformat() == "2040-09-09"
    first = business_day_service.get_or_create_current_business_day(db, after)
    second = business_day_service.get_or_create_current_business_day(db, after)
    assert first.id == second.id
    assert db.scalar(select(func.count()).select_from(BusinessDay).where(BusinessDay.business_date == after.date())) == 1


def test_order_totals_gosht_snapshot_and_number(db: Session) -> None:
    osh, _, _, option, _, egg, meat, _, _, admin = _catalog(db)
    first = order_service.create_order(db, _order(osh.id, option.id, [
        {"addon_id": egg.id, "quantity": "1"},
        {"addon_id": meat.id, "quantity": "1", "manual_price": 15000},
    ]), actor_id=admin.id)
    second = order_service.create_order(db, _order(osh.id, option.id, [{"addon_id": meat.id, "quantity": "1", "manual_price": 23000}]), actor_id=admin.id)
    assert first.order_number.isdigit() and first.order_number != second.order_number
    assert first.total_amount == 47000
    first_meat = next(addon for addon in first.items[0].addons if addon.addon_id == meat.id)
    second_meat = next(addon for addon in second.items[0].addons if addon.addon_id == meat.id)
    assert first_meat.unit_price == 15000
    assert first_meat.manual_price == 15000
    assert first_meat.price_option_id is None
    assert second_meat.unit_price == 23000
    assert next(addon for addon in order_service.get_order(db, first.id).items[0].addons if addon.addon_id == meat.id).unit_price == 15000


def test_half_quantity_base_price_delivery_and_filters(db: Session) -> None:
    osh, other, _, option, _, _, _, _, worker, admin = _catalog(db)
    half = OrderCreate.model_validate({"order_type": "CHAYKHANA", "items": [{"product_id": osh.id, "quantity": "0.5", "selected_price_option_id": option.id}]})
    created = order_service.create_order(db, half, actor_id=admin.id)
    delivery = order_service.create_order(db, _order(other.id, None, order_type="DELIVERY", delivery_worker_id=worker.id), actor_id=admin.id)
    assert created.total_amount == 15000
    assert delivery.delivery_worker_id == worker.id
    assert order_service.list_orders(db, created.business_day.business_date, None, OrderType.CHAYKHANA, None, 50, 0)[0].id == created.id


@pytest.mark.parametrize("payload", [
    {"order_type": "DELIVERY", "items": []},
    {"order_type": "CHAYKHANA", "items": [{"product_id": 1, "quantity": "0"}]},
])
def test_invalid_order_shapes_are_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        OrderCreate.model_validate(payload)


def test_order_rejects_invalid_catalog_and_is_atomic(db: Session) -> None:
    osh, _, unpriced, option, inactive_option, _, meat, inactive, _, admin = _catalog(db)
    admin_id = admin.id
    count_before = db.scalar(select(func.count()).select_from(Order))
    cases = [
        _order(999999, None),
        _order(unpriced.id, None),
        _order(osh.id, inactive_option.id),
        _order(osh.id, option.id, [{"addon_id": inactive.id, "quantity": "1"}]),
        _order(osh.id, option.id, [{"addon_id": meat.id, "quantity": "1", "selected_price_option_id": option.id, "manual_price": 1000}]),
        _order(osh.id, option.id, [{"addon_id": meat.id, "quantity": "1"}]),
    ]
    for payload in cases:
        with pytest.raises(ServiceError):
            order_service.create_order(db, payload, actor_id=admin_id)
        assert db.scalar(select(func.count()).select_from(Order)) == count_before
