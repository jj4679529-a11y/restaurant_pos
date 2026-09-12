from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AddOn, Category, ManualPricePreset, PriceOption, Product, ProductAddOn, UnitType
from app.seed.catalog import CATEGORIES, OSH_ADDONS, PRODUCTS
from app.seed.config import SeedResult, SeedSettings
from decimal import Decimal


def seed_categories(session: Session, result: SeedResult) -> dict[str, Category]:
    by_name: dict[str, Category] = {}
    for spec in CATEGORIES:
        category = session.scalars(select(Category).where(Category.name == spec.name)).one_or_none()
        if category is None:
            category = Category(name=spec.name, sort_order=spec.sort_order, is_active=True)
            session.add(category)
            session.flush()
            result.categories_created += 1
        by_name[spec.name] = category
    return by_name


def seed_products(session: Session, categories: dict[str, Category], result: SeedResult) -> dict[str, Product]:
    by_name: dict[str, Product] = {}
    for spec in PRODUCTS:
        category = categories[spec.category_name]
        product = session.scalars(
            select(Product).where(Product.category_id == category.id, Product.name == spec.name)
        ).one_or_none()
        if product is None:
            product = Product(
                category_id=category.id,
                name=spec.name,
                unit_type=spec.unit_type,
                base_price=spec.base_price,
                allows_manual_price=spec.allows_manual_price,
                is_active=True,
            )
            session.add(product)
            session.flush()
            result.products_created += 1
        by_name[spec.name] = product

        for option in spec.price_options:
            existing_option = session.scalars(
                select(PriceOption).where(
                    PriceOption.product_id == product.id,
                    PriceOption.price == option.price,
                )
            ).one_or_none()
            if existing_option is not None:
                continue
            session.add(
                PriceOption(
                    product_id=product.id,
                    name=str(option.price),
                    quantity=option.quantity,
                    price=option.price,
                    is_active=True,
                )
            )
            result.price_options_created += 1
    return by_name


def seed_osh_addons(session: Session, osh: Product, result: SeedResult) -> None:
    for spec in OSH_ADDONS:
        addon = session.scalars(select(AddOn).where(AddOn.name == spec.name)).one_or_none()
        if addon is None:
            addon = AddOn(
                name=spec.name,
                unit_type=spec.unit_type,
                base_price=spec.base_price,
                allows_manual_price=spec.allows_manual_price,
                is_active=True,
            )
            session.add(addon)
            session.flush()
            result.addons_created += 1

        link = session.scalars(
            select(ProductAddOn).where(
                ProductAddOn.product_id == osh.id,
                ProductAddOn.addon_id == addon.id,
            )
        ).one_or_none()
        if link is None:
            session.add(
                ProductAddOn(
                    product_id=osh.id,
                    addon_id=addon.id,
                    is_required=False,
                    is_active=True,
                )
            )
            result.product_addons_created += 1


def seed_final_pricing(session: Session, products: dict[str, Product], settings: SeedSettings, result: SeedResult) -> None:
    """Transition legacy menu once; subsequent runs preserve Admin-edited prices.

    Old price-option IDs are retained inactive because order history references
    them. New portion prices are explicit restaurant configuration, never guesses.
    """
    osh = products["Osh"]
    osh.allows_manual_price = False
    osh.base_price = 0
    osh.unit_type = UnitType.PORTION
    products["Jizz"].allows_manual_price = True
    for option in session.scalars(select(PriceOption).where(PriceOption.product_id == products["Jizz"].id)):
        option.is_active = False
    options = session.scalars(select(PriceOption).where(PriceOption.product_id == osh.id).with_for_update()).all()
    selected = []
    for portion, amount in ((Decimal("0.5"), settings.OSH_HALF_PRICE), (Decimal("1"), settings.OSH_FULL_PRICE)):
        name = f"{portion} porsiya"
        option = next((o for o in options if o.name == name and o.quantity == portion), None)
        if option is None:
            if amount is None:
                raise ValueError("Set OSH_HALF_PRICE and OSH_FULL_PRICE before configuring the final Osh menu")
            option = PriceOption(product_id=osh.id, name=name, quantity=portion, price=amount, is_active=True)
            session.add(option)
            result.price_options_created += 1
        option.is_active = True
        selected.append(option)
    for option in options:
        if option not in selected:
            option.is_active = False

    for name, amount in (("Tuxum 1", settings.EGG_ONE_PRICE), ("Tuxum 2", settings.EGG_TWO_PRICE), ("Qazi", settings.QAZI_PRICE)):
        addon = session.scalars(select(AddOn).where(AddOn.name == name)).one()
        addon.allows_manual_price = False
        addon.unit_type = UnitType.PIECE
        if addon.base_price == 0 and amount is not None:
            addon.base_price = amount
    gosht = session.scalars(select(AddOn).where(AddOn.name == "Go'sht")).one()
    gosht.allows_manual_price = True
    for target, amounts, field in ((gosht, settings.GOSHT_MANUAL_PRESETS, "addon_id"), (products["Jizz"], settings.JIZZ_MANUAL_PRESETS, "product_id")):
        # Seed only an empty preset collection; respect later Admin edits/removals.
        if session.scalars(select(ManualPricePreset).where(getattr(ManualPricePreset, field) == target.id)).first() is None:
            for position, amount in enumerate(dict.fromkeys(amounts)):
                if type(amount) is not int or amount <= 0:
                    raise ValueError("Manual price presets must be positive integer UZS")
                session.add(ManualPricePreset(**{field: target.id}, amount=amount, sort_order=position, is_active=True))
