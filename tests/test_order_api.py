from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import AddOn, Category, PriceOption, Product, ProductAddOn, UnitType, UserRole
from tests.auth_helpers import cashier_headers, create_test_user
from main import app


def test_order_response_serializes_manual_gosht_price_option_as_null(db: Session) -> None:
    suffix = uuid4().hex[:8]
    category = Category(name=f"Order API {suffix}", sort_order=1, is_active=True)
    osh = Product(
        category=category,
        name=f"Osh API {suffix}",
        unit_type=UnitType.PORTION,
        base_price=0,
        allows_manual_price=False,
        is_active=True,
    )
    price_option = PriceOption(
        product=osh,
        name="15000",
        quantity=Decimal("1.000"),
        price=15000,
        is_active=True,
    )
    gosht = AddOn(
        name=f"Go'sht API {suffix}",
        unit_type=UnitType.AMOUNT,
        base_price=0,
        allows_manual_price=True,
        is_active=True,
    )
    tuxum = AddOn(
        name=f"Tuxum API {suffix}",
        unit_type=UnitType.PIECE,
        base_price=2000,
        allows_manual_price=False,
        is_active=True,
    )
    db.add_all([category, osh, price_option, gosht, tuxum])
    db.flush()
    db.add(ProductAddOn(product_id=osh.id, addon_id=gosht.id, is_required=False, is_active=True))
    db.add(ProductAddOn(product_id=osh.id, addon_id=tuxum.id, is_required=False, is_active=True))
    cashier = create_test_user(
        db,
        name="Order Cashier",
        username=f"order-cashier-{suffix}",
        role=UserRole.CASHIER,
    )
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=cashier_headers(cashier)) as client:
            response = client.post("/api/orders", json={
                "order_type": "CHAYKHANA",
                "items": [{
                    "product_id": osh.id,
                    "quantity": 1,
                    "selected_price_option_id": price_option.id,
                    "addons": [{"addon_id": gosht.id, "quantity": 1, "manual_price": 15000}],
                }],
            })
            assert response.status_code == 201, response.text
            body = response.json()
            item = body["items"][0]
            addon = item["addons"][0]
            assert item["selected_price_option_id"] == price_option.id
            assert addon["selected_price_option_id"] is None
            assert addon["manual_price"] == 15000
            assert addon["unit_price"] == 15000
            assert addon["total_price"] == 15000
            assert body["total_amount"] == 30000
            assert body["payment_status"] == "PENDING"

            no_addons = client.post("/api/orders", json={
                "order_type": "CHAYKHANA",
                "items": [{
                    "product_id": osh.id,
                    "quantity": 1,
                    "selected_price_option_id": price_option.id,
                    "addons": [],
                }],
            })
            assert no_addons.status_code == 201, no_addons.text
            assert no_addons.json()["items"][0]["addons"] == []
            assert no_addons.json()["items"][0]["selected_price_option_id"] == price_option.id

            normal_addon = client.post("/api/orders", json={
                "order_type": "CHAYKHANA",
                "items": [{
                    "product_id": osh.id,
                    "quantity": 1,
                    "selected_price_option_id": price_option.id,
                    "addons": [{"addon_id": tuxum.id, "quantity": 1}],
                }],
            })
            assert normal_addon.status_code == 201, normal_addon.text
            addon = normal_addon.json()["items"][0]["addons"][0]
            assert addon["selected_price_option_id"] is None
            assert addon["manual_price"] is None
            assert addon["unit_price"] == 2000
    finally:
        app.dependency_overrides.clear()
