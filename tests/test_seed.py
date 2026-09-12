from pathlib import Path
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AddOn, Category, DeliveryWorker, PriceOption, Product, ProductAddOn, Setting, User, UserRole
from app.seed.catalog import CATEGORIES, DEMO_DELIVERY_WORKERS, PRODUCTS
from app.seed.config import SeedSettings
from app.seed.passwords import verify_password
from app.seed.runner import seed_all

TEST_ADMIN_USERNAME = "seed_test_admin"
SEED_PASSWORD = "seed-test-password"


def _settings() -> SeedSettings:
    return SeedSettings(
        ADMIN_USERNAME=TEST_ADMIN_USERNAME,
        ADMIN_PASSWORD=SEED_PASSWORD,
        ADMIN_NAME="Administrator",
        OSH_HALF_PRICE=17000,
        OSH_FULL_PRICE=31000,
        EGG_ONE_PRICE=3000,
        EGG_TWO_PRICE=5000,
        QAZI_PRICE=8000,
        GOSHT_MANUAL_PRESETS=[10000, 15000, 20000],
        JIZZ_MANUAL_PRESETS=[60000, 70000, 80000],
    )


def test_seed_settings_allows_blank_admin_password() -> None:
    settings = SeedSettings(ADMIN_USERNAME=TEST_ADMIN_USERNAME, ADMIN_PASSWORD="")

    assert settings.ADMIN_PASSWORD == ""


def _seed(db: Session) -> None:
    seed_all(db, _settings())
    db.flush()


def test_gitignore_includes_env() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in {line.strip() for line in gitignore.splitlines()}


def test_admin_is_created_once(db: Session) -> None:
    first = seed_all(db, _settings())
    db.flush()
    second = seed_all(db, _settings())
    db.flush()

    admins = db.scalars(select(User).where(User.username == TEST_ADMIN_USERNAME)).all()
    assert first.admin_created is True
    assert "Admin created" in first.messages
    assert second.admin_created is False
    assert "Admin already exists" in second.messages
    assert len(admins) == 1
    assert admins[0].role is UserRole.ADMIN
    assert admins[0].is_active is True


def test_admin_password_is_hashed(db: Session) -> None:
    _seed(db)
    admin = db.scalars(select(User).where(User.username == TEST_ADMIN_USERNAME)).one()
    assert admin.password_hash != SEED_PASSWORD
    assert SEED_PASSWORD not in admin.password_hash
    assert verify_password(SEED_PASSWORD, admin.password_hash)


def test_categories_and_products(db: Session) -> None:
    _seed(db)
    category_names = set(db.scalars(select(Category.name)).all())
    assert {spec.name for spec in CATEGORIES} <= category_names

    osh = db.scalars(select(Product).where(Product.name == "Osh")).one()
    assert osh.category.name == "Milliy taomlar"
    assert osh.unit_type.value == "PORTION"

    for spec in PRODUCTS:
        product = db.scalars(select(Product).where(Product.name == spec.name)).one()
        assert product.category.name == spec.category_name


def test_osh_price_options_are_configurable(db: Session) -> None:
    _seed(db)
    osh = db.scalars(select(Product).where(Product.name == "Osh")).one()
    prices = sorted(db.scalars(select(PriceOption.price).where(PriceOption.product_id == osh.id, PriceOption.is_active.is_(True))).all())
    assert prices == [17000, 31000]
    assert sorted(option.quantity for option in osh.price_options if option.is_active) == [Decimal("0.5"), Decimal("1")]


def test_osh_addons_and_gosht_is_not_a_product(db: Session) -> None:
    _seed(db)
    osh = db.scalars(select(Product).where(Product.name == "Osh")).one()
    addon_names = set(
        db.scalars(
            select(AddOn.name)
            .join(ProductAddOn, ProductAddOn.addon_id == AddOn.id)
            .where(ProductAddOn.product_id == osh.id)
        ).all()
    )
    assert addon_names == {"Tuxum 1", "Tuxum 2", "Qazi", "Go'sht"}
    gosht_products = db.scalars(select(Product).where(Product.name == "Go'sht")).all()
    assert gosht_products == []
    gosht = db.scalars(select(AddOn).where(AddOn.name == "Go'sht")).one()
    assert gosht.allows_manual_price is True
    assert gosht.unit_type.value == "AMOUNT"
    gosht_price_options = db.scalars(
        select(PriceOption).join(Product).where(Product.name == "Go'sht")
    ).all()
    assert gosht_price_options == []


def test_delivery_workers_and_settings(db: Session) -> None:
    _seed(db)
    worker_names = set(db.scalars(select(DeliveryWorker.name)).all())
    assert {spec.name for spec in DEMO_DELIVERY_WORKERS} <= worker_names
    setting_keys = set(db.scalars(select(Setting.key)).all())
    assert {"restaurant_name", "business_day_start", "timezone"} <= setting_keys
    assert "gosht_price_options" not in setting_keys
    restaurant_name = db.scalars(select(Setting).where(Setting.key == "restaurant_name")).one()
    assert restaurant_name.value == "Restaurant POS"


def test_seed_is_idempotent(db: Session) -> None:
    first = seed_all(db, _settings())
    db.flush()
    product_names = [item.name for item in PRODUCTS]
    category_names = [item.name for item in CATEGORIES]
    worker_names = [item.name for item in DEMO_DELIVERY_WORKERS]
    counts_after_first = {
        "users": db.scalar(select(func.count()).select_from(User).where(User.username == TEST_ADMIN_USERNAME)),
        "categories": db.scalar(select(func.count()).select_from(Category).where(Category.name.in_(category_names))),
        "products": db.scalar(select(func.count()).select_from(Product).where(Product.name.in_(product_names))),
        "addons": db.scalar(select(func.count()).select_from(AddOn)),
        "workers": db.scalar(
            select(func.count()).select_from(DeliveryWorker).where(DeliveryWorker.name.in_(worker_names))
        ),
    }
    second = seed_all(db, _settings())
    db.flush()
    counts_after_second = {
        "users": db.scalar(select(func.count()).select_from(User).where(User.username == TEST_ADMIN_USERNAME)),
        "categories": db.scalar(select(func.count()).select_from(Category).where(Category.name.in_(category_names))),
        "products": db.scalar(select(func.count()).select_from(Product).where(Product.name.in_(product_names))),
        "addons": db.scalar(select(func.count()).select_from(AddOn)),
        "workers": db.scalar(
            select(func.count()).select_from(DeliveryWorker).where(DeliveryWorker.name.in_(worker_names))
        ),
    }

    assert counts_after_first == counts_after_second
    assert counts_after_second["users"] == 1
    assert counts_after_second["categories"] == len(CATEGORIES)
    assert counts_after_second["products"] == len(PRODUCTS)
    assert counts_after_second["addons"] == 4
    assert second.products_created == 0
    assert second.categories_created == 0
    assert second.delivery_workers_created == 0
    assert second.settings_created == 0
    assert first.admin_created is True
