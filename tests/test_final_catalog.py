from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.product_images import resolve_product_image
from app.core.config import get_settings
from app.database.connection import get_db
from app.models import AddOn, Category, ManualPricePreset, PriceOption, Product, ProductAddOn, UnitType, UserRole
from app.schemas.catalog import ImageReference
from app.schemas.orders import OrderCreate
from app.seed.runner import seed_all
from app.services import order_service
from app.services.errors import ServiceError
from app.ui.state import Cart, CartAddOn, CartItem
from tests.auth_helpers import auth_headers, create_test_user
from tests.test_seed import _settings
from main import app


@pytest.fixture
def catalog(db):
    suffix = uuid4().hex[:8]
    category = Category(name=f"Final menu {suffix}")
    product = Product(category=category, name=f"Jizz {suffix}", unit_type=UnitType.AMOUNT,
                      base_price=0, allows_manual_price=True)
    addon = AddOn(name=f"Go'sht {suffix}", unit_type=UnitType.AMOUNT, base_price=0, allows_manual_price=True)
    db.add_all([product, addon])
    db.flush()
    db.add(ProductAddOn(product_id=product.id, addon_id=addon.id))
    db.flush()
    return product.id, addon.id


def test_presets_admin_edit_and_catalog_serialization(db, catalog):
    product_id, addon_id = catalog
    admin = create_test_user(db, name="Admin", username=f"preset-{uuid4().hex}")
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=auth_headers(admin)) as client:
            product_preset = client.post("/api/manual-price-presets", json={"product_id": product_id, "amount": 70000})
            assert product_preset.status_code == 201, product_preset.text
            addon_preset = client.post("/api/manual-price-presets", json={"addon_id": addon_id, "amount": 15000})
            assert addon_preset.status_code == 201, addon_preset.text
            assert addon_preset.json()["product_id"] is None
            assert addon_preset.json()["addon_id"] == addon_id
            assert client.patch(f"/api/products/{product_id}", json={"image_path": "menu/jizz.png"}).status_code == 200
            preset_id = product_preset.json()["id"]
            assert client.patch(f"/api/manual-price-presets/{preset_id}", json={"amount": 73000}).status_code == 200
            detail = client.get(f"/api/products/{product_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["image_path"] == "menu/jizz.png"
            assert detail.json()["manual_price_presets"][0]["amount"] == 73000
            assert detail.json()["available_addons"][0]["manual_price_presets"][0]["amount"] == 15000
            assert client.patch(f"/api/manual-price-presets/{preset_id}", json={"is_active": False}).status_code == 200
            assert client.get(f"/api/products/{product_id}").json()["manual_price_presets"] == []
            assert client.get(f"/api/manual-price-presets?product_id={product_id}").json() == []
    finally:
        app.dependency_overrides.clear()


def test_cashier_reads_but_cannot_edit_presets(db, catalog):
    user = create_test_user(db, name="Cashier", username=f"preset-{uuid4().hex}", role=UserRole.CASHIER)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=auth_headers(user)) as client:
            assert client.get("/api/manual-price-presets").status_code == 200
            assert client.post("/api/manual-price-presets", json={"product_id": catalog[0], "amount": 1}).status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("targets", ["none", "both", "zero", "duplicate"])
def test_database_preset_constraints(db, catalog, targets):
    product_id, addon_id = catalog
    values = {"amount": 10000}
    if targets == "both":
        values.update(product_id=product_id, addon_id=addon_id)
    elif targets == "zero":
        values.update(product_id=product_id, amount=0)
    elif targets == "duplicate":
        values.update(product_id=product_id)
        db.add(ManualPricePreset(**values))
        db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(ManualPricePreset(**values))
            db.flush()


@pytest.mark.parametrize("reference", ["../secret.png", "/etc/photo.png", "C:\\photo.png", "https://host/photo.png", "photo.svg"])
def test_image_reference_rejects_nonlocal_paths(reference):
    with pytest.raises(ValidationError):
        ImageReference(image_path=reference)


def test_authenticated_local_image_and_traversal(db, tmp_path, monkeypatch):
    media = tmp_path / "media"
    media.mkdir()
    content = b"local-fixture-image"
    (media / "food.png").write_bytes(content)
    (tmp_path / "outside.png").write_bytes(b"private")
    (media / "escape.png").symlink_to(tmp_path / "outside.png")
    for reference in ("../outside.png", "escape.png", "missing.png"):
        with pytest.raises(ServiceError):
            resolve_product_image(media, reference)
    monkeypatch.setenv("PRODUCT_MEDIA_DIR", str(media))
    get_settings.cache_clear()
    user = create_test_user(db, name="Cashier", username=f"image-{uuid4().hex}", role=UserRole.CASHIER)
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            assert client.get("/api/product-images/food.png").status_code == 401
            response = client.get("/api/product-images/food.png", headers=auth_headers(user))
            assert response.status_code == 200 and response.content == content
    finally:
        app.dependency_overrides.clear()


def test_seed_legacy_transition_preserves_history_admin_prices_and_presets(db):
    settings = _settings()
    seed_all(db, settings)
    db.flush()
    osh = db.scalar(select(Product).where(Product.name == "Osh"))
    half = db.scalar(select(PriceOption).where(PriceOption.product_id == osh.id, PriceOption.name == "0.5 porsiya"))
    half.price = 18500
    legacy = PriceOption(product_id=osh.id, name="legacy fixture", quantity=1, price=45678, is_active=True)
    db.add(legacy)
    db.flush()
    legacy_id = legacy.id
    before = db.scalar(select(func.count()).select_from(ManualPricePreset))
    preset = db.scalars(select(ManualPricePreset)).first()
    preset.amount += 123
    edited_amount, preset_id = preset.amount, preset.id
    seed_all(db, settings)
    db.flush()
    seed_all(db, settings)
    db.flush()
    assert db.get(PriceOption, legacy_id).is_active is False
    assert db.get(PriceOption, legacy_id).price == 45678
    active = db.scalars(select(PriceOption).where(PriceOption.product_id == osh.id, PriceOption.is_active.is_(True))).all()
    assert sorted((o.quantity, o.price) for o in active) == [(Decimal("0.5"), 18500), (Decimal("1"), 31000)]
    assert db.scalar(select(func.count()).select_from(ManualPricePreset)) == before
    assert db.get(ManualPricePreset, preset_id).amount == edited_amount
    assert db.scalar(select(Product).where(Product.name == "Jizz")).allows_manual_price
    assert db.scalar(select(Product).where(Product.name == "Go'sht")) is None


@pytest.mark.parametrize("portion,price", [("0.5 porsiya", 17000), ("1 porsiya", 31000)])
def test_portion_cart_payload_matches_production_order_totals(db, portion, price):
    seed_all(db, _settings())
    db.flush()
    osh = db.scalar(select(Product).where(Product.name == "Osh"))
    option = db.scalar(select(PriceOption).where(PriceOption.product_id == osh.id, PriceOption.name == portion))
    gosht = db.scalar(select(AddOn).where(AddOn.name == "Go'sht"))
    actor = create_test_user(db, name="Cashier", username=f"portion-{uuid4().hex}", role=UserRole.CASHIER)
    cart = Cart()
    cart.add(CartItem.from_catalog({"id": osh.id, "name": "Osh"}, Decimal(1),
        {"id": option.id, "name": portion, "price": option.price},
        addons=(CartAddOn(gosht.id, gosht.name, Decimal("1.000"), 15000, 15000),)))
    order = order_service.create_order(db, OrderCreate(**cart.order_payload("CHAYKHANA")), actor_id=actor.id)
    assert order.total_amount == cart.total_amount == price + 15000
    assert order.items[0].unit_price == price
    assert order.items[0].addons[0].price_option_id is None
    assert order.items[0].addons[0].manual_price == 15000
