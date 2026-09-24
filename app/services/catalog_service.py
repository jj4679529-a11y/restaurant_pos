from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import AddOn, Category, PriceOption, Product, ProductAddOn
from app.schemas.catalog import (
    AddOnCreate, AddOnUpdate, CategoryCreate, CategoryUpdate, PriceOptionCreate,
    PriceOptionUpdate, ProductCreate, ProductUpdate,
)
from app.services.errors import ServiceError, conflict, not_found
from app.menu_rules import menu_key, OSH_ADDONS, PIECE_DRINKS


def validate_menu_product(name, unit_type, manual):
    key = menu_key(name)
    if key == 'gosht':
        raise ServiceError(400, 'addon_only', 'Go‘sht is an Osh addon, not a product')
    if key in PIECE_DRINKS and (unit_type.value != 'PIECE' or manual):
        raise ServiceError(400, 'piece_price_required', 'Kompot and Ayron require piece pricing')
    if key == 'jizz' and not manual:
        raise ServiceError(400, 'manual_price_required', 'Jizz requires cashier-entered amount')


def _commit(session: Session, item: object) -> object:
    try:
        session.add(item)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("A record with those values already exists") from exc
    session.refresh(item)
    return item


def _product_query() -> Select[tuple[Product]]:
    return select(Product).execution_options(populate_existing=True).options(
        selectinload(Product.price_options),
        selectinload(Product.manual_price_presets),
        selectinload(Product.product_addons).selectinload(ProductAddOn.addon).selectinload(AddOn.manual_price_presets),
    )


def list_categories(session: Session, include_inactive: bool, limit: int, offset: int) -> Sequence[Category]:
    query = select(Category).order_by(Category.sort_order, Category.id).limit(limit).offset(offset)
    if not include_inactive:
        query = query.where(Category.is_active.is_(True))
    return session.scalars(query).all()


def get_category(session: Session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise not_found("Category")
    return category


def create_category(session: Session, data: CategoryCreate) -> Category:
    if session.scalars(select(Category).where(Category.name == data.name)).one_or_none():
        raise conflict("A category with this name already exists")
    return _commit(session, Category(**data.model_dump()))  # type: ignore[return-value]


def update_category(session: Session, category_id: int, data: CategoryUpdate) -> Category:
    category = get_category(session, category_id)
    values = data.model_dump(exclude_unset=True)
    if "name" in values and session.scalars(select(Category).where(Category.name == values["name"], Category.id != category_id)).one_or_none():
        raise conflict("A category with this name already exists")
    for field, value in values.items():
        setattr(category, field, value)
    return _commit(session, category)  # type: ignore[return-value]


def list_products(session: Session, category_id: int | None, is_active: bool | None, search: str | None, limit: int, offset: int) -> Sequence[Product]:
    query = _product_query().order_by(Product.id).limit(limit).offset(offset)
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    query = query.where(Product.is_active.is_(True) if is_active is None else Product.is_active.is_(is_active))
    if search:
        query = query.where(Product.name.ilike(f"%{search.strip()}%"))
    return session.scalars(query).all()


def get_product(session: Session, product_id: int) -> Product:
    product = session.scalars(_product_query().where(Product.id == product_id)).one_or_none()
    if product is None:
        raise not_found("Product")
    return product


def create_product(session: Session, data: ProductCreate) -> Product:
    validate_menu_product(data.name, data.unit_type, data.allows_manual_price)
    category = session.get(Category, data.category_id)
    if category is None:
        raise not_found("Category")
    return get_product(session, _commit(session, Product(**data.model_dump())).id)  # type: ignore[union-attr]


def update_product(session: Session, product_id: int, data: ProductUpdate) -> Product:
    product = get_product(session, product_id)
    values = data.model_dump(exclude_unset=True)
    if "category_id" in values and session.get(Category, values["category_id"]) is None:
        raise not_found("Category")
    validate_menu_product(values.get('name', product.name), values.get('unit_type', product.unit_type),
                          values.get('allows_manual_price', product.allows_manual_price))
    for field, value in values.items():
        setattr(product, field, value)
    _commit(session, product)
    return get_product(session, product_id)


def list_price_options(session: Session, product_id: int, limit: int, offset: int) -> Sequence[PriceOption]:
    get_product(session, product_id)
    return session.scalars(select(PriceOption).where(PriceOption.product_id == product_id).order_by(PriceOption.id).limit(limit).offset(offset)).all()


def create_price_option(session: Session, product_id: int, data: PriceOptionCreate) -> PriceOption:
    product = get_product(session, product_id)
    if not product.is_active:
        raise ServiceError(400, "inactive_product", "Cannot add a price option to an inactive product")
    duplicate = session.scalars(select(PriceOption).where(PriceOption.product_id == product_id, PriceOption.price == data.price)).one_or_none()
    if duplicate:
        raise conflict("A price option with this price already exists for the product")
    return _commit(session, PriceOption(product_id=product_id, **data.model_dump()))  # type: ignore[return-value]


def update_price_option(session: Session, price_option_id: int, data: PriceOptionUpdate) -> PriceOption:
    option = session.get(PriceOption, price_option_id)
    if option is None:
        raise not_found("Price option")
    values = data.model_dump(exclude_unset=True)
    price = values.get("price")
    if price is not None and session.scalars(select(PriceOption).where(PriceOption.product_id == option.product_id, PriceOption.price == price, PriceOption.id != option.id)).one_or_none():
        raise conflict("A price option with this price already exists for the product")
    for field, value in values.items():
        setattr(option, field, value)
    return _commit(session, option)  # type: ignore[return-value]


def list_addons(session: Session, include_inactive: bool, limit: int, offset: int) -> Sequence[AddOn]:
    query = select(AddOn).order_by(AddOn.id).limit(limit).offset(offset)
    if not include_inactive:
        query = query.where(AddOn.is_active.is_(True))
    return session.scalars(query).all()


def get_addon(session: Session, addon_id: int) -> AddOn:
    addon = session.get(AddOn, addon_id)
    if addon is None:
        raise not_found("Add-on")
    return addon


def create_addon(session: Session, data: AddOnCreate) -> AddOn:
    return _commit(session, AddOn(**data.model_dump()))  # type: ignore[return-value]


def update_addon(session: Session, addon_id: int, data: AddOnUpdate) -> AddOn:
    addon = get_addon(session, addon_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(addon, field, value)
    return _commit(session, addon)  # type: ignore[return-value]


def link_addon(session: Session, product_id: int, addon_id: int) -> ProductAddOn:
    product = get_product(session, product_id)
    addon = get_addon(session, addon_id)
    if menu_key(addon.name) in OSH_ADDONS and 'osh' not in menu_key(product.name):
        raise ServiceError(400, 'osh_addon_only', 'This addon is available only for Osh')
    if not product.is_active or not addon.is_active:
        raise ServiceError(400, "inactive_catalog_item", "Inactive products or add-ons cannot be linked")
    existing = session.scalars(select(ProductAddOn).where(ProductAddOn.product_id == product_id, ProductAddOn.addon_id == addon_id)).one_or_none()
    if existing:
        raise conflict("Product and add-on are already linked")
    return _commit(session, ProductAddOn(product_id=product_id, addon_id=addon_id, is_required=False, is_active=True))  # type: ignore[return-value]
