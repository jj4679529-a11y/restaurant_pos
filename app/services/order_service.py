from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AddOn, BusinessDay, DeliveryWorker, Order, OrderItem, OrderItemAddOn,
    OrderType, PaymentStatus, PriceOption, Product, ProductAddOn, User,
)
from app.schemas.orders import OrderCreate, OrderItemAddOnCreate, OrderItemCreate
from app.services import business_day_service
from app.services.errors import ServiceError, conflict, not_found
from app.menu_rules import menu_key, OSH_ADDONS, PIECE_DRINKS


def _order_query():
    return select(Order).options(
        selectinload(Order.business_day),
        selectinload(Order.delivery_worker),
        selectinload(Order.canceller),
        selectinload(Order.items).selectinload(OrderItem.product),
        selectinload(Order.items).selectinload(OrderItem.addons).selectinload(OrderItemAddOn.addon),
    )


def _integer_money(value: Decimal, label: str) -> int:
    if value <= 0 or value != value.to_integral_value():
        raise ServiceError(400, "invalid_total", f"{label} must be a positive whole so'm amount")
    return int(value)


def _get_active_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    if not product.is_active:
        raise ServiceError(400, "inactive_product", "Product is inactive")
    return product


def _product_price(session: Session, product: Product, item: OrderItemCreate) -> tuple[int, int | None, int | None]:
    if menu_key(product.name) in PIECE_DRINKS and product.unit_type.value != 'PIECE':
        raise ServiceError(400, 'piece_price_required', 'Admin must configure this drink with a price per piece')
    if item.manual_price is not None:
        if not product.allows_manual_price:
            raise ServiceError(400, "manual_price_not_allowed", "This product does not allow a manual price")
        if item.selected_price_option_id is not None:
            raise ServiceError(400, "invalid_price_option", "Manual-price products cannot use a price option")
        return item.manual_price, None, item.manual_price

    active_options = session.scalars(
        select(PriceOption).where(PriceOption.product_id == product.id, PriceOption.is_active.is_(True))
    ).all()
    if active_options:
        if item.selected_price_option_id is None:
            raise ServiceError(400, "price_option_required", "An active price option must be selected for this product")
        selected = next((option for option in active_options if option.id == item.selected_price_option_id), None)
        if selected is None:
            raise ServiceError(400, "invalid_price_option", "Price option is inactive or does not belong to this product")
        return selected.price, selected.id, None

    if item.selected_price_option_id is not None:
        raise ServiceError(400, "invalid_price_option", "This product has no active price options")
    if product.base_price <= 0:
        raise ServiceError(400, "unconfigured_product_price", "Product has no configured price")
    return product.base_price, None, None


def _addon_price(session: Session, product: Product, addon_input: OrderItemAddOnCreate) -> tuple[AddOn, int, int | None]:
    addon = session.get(AddOn, addon_input.addon_id)
    if addon is None:
        raise not_found("Add-on")
    if menu_key(addon.name) in OSH_ADDONS and menu_key(product.name) != 'osh':
        raise ServiceError(400, 'osh_addon_only', 'This addon is available only for Osh')
    if menu_key(addon.name) == 'gosht' and (addon_input.manual_price is None or addon_input.manual_price < 5000):
        raise ServiceError(400, 'gosht_minimum', 'Go‘sht amount must be at least 5000 UZS')
    if not addon.is_active:
        raise ServiceError(400, "inactive_addon", "Add-on is inactive")
    link = session.scalars(
        select(ProductAddOn).where(
            ProductAddOn.product_id == product.id,
            ProductAddOn.addon_id == addon.id,
            ProductAddOn.is_active.is_(True),
        )
    ).one_or_none()
    if link is None:
        raise ServiceError(400, "addon_not_available", "Add-on is not active for this product")
    if addon_input.selected_price_option_id is not None:
        raise ServiceError(400, "invalid_addon_price_option", "Add-ons cannot use price options")

    if addon.allows_manual_price:
        if addon_input.manual_price is None:
            raise ServiceError(400, "manual_price_required", "This add-on requires a manual price")
        return addon, addon_input.manual_price, addon_input.manual_price
    if addon_input.manual_price is not None:
        raise ServiceError(400, "manual_price_not_allowed", "This add-on uses its configured base price")
    if addon.base_price <= 0:
        raise ServiceError(400, "unconfigured_addon_price", "Add-on has no configured base price")
    return addon, addon.base_price, None


def _delivery_worker(session: Session, payload: OrderCreate) -> DeliveryWorker | None:
    if payload.order_type is OrderType.CHAYKHANA:
        if payload.delivery_worker_id is not None:
            raise ServiceError(400, "invalid_delivery_worker", "CHAYKHANA orders cannot have a delivery worker")
        return None
    if payload.delivery_worker_id is None:
        raise ServiceError(400, "delivery_worker_required", "DELIVERY orders require a delivery worker")
    worker = session.get(DeliveryWorker, payload.delivery_worker_id)
    if worker is None:
        raise not_found("Delivery worker")
    if not worker.is_active:
        raise ServiceError(400, "inactive_delivery_worker", "Delivery worker is inactive")
    return worker


def _creator(session: Session, actor_id: int) -> User:
    user = session.get(User, actor_id)
    if user is None or not user.is_active:
        raise ServiceError(409, "ORDER_ACTOR_NOT_AVAILABLE", "Order actor is not active")
    return user


def create_order(session: Session, payload: OrderCreate, actor_id: int) -> Order:
    try:
        business_day = business_day_service.ensure_open_business_day(session)
        worker = _delivery_worker(session, payload)
        order = Order(
            # A UUID temporary value satisfies the NOT NULL/unique column while
            # PostgreSQL allocates the sequence-backed order id on flush.
            order_number=uuid4().hex,
            business_day_id=business_day.id,
            order_type=payload.order_type,
            delivery_worker_id=worker.id if worker else None,
            created_by=_creator(session, actor_id).id,
            payment_status=PaymentStatus.PENDING,
            total_amount=0,
        )
        session.add(order)
        session.flush()
        order.order_number = f"{order.id:05d}"

        total = 0
        for item_input in payload.items:
            product = _get_active_product(session, item_input.product_id)
            unit_price, selected_price_option_id, manual_price = _product_price(session, product, item_input)
            product_total = _integer_money(item_input.quantity * unit_price, "Product subtotal")
            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item_input.quantity,
                unit_price=unit_price,
                total_price=product_total,
                selected_price_option_id=selected_price_option_id,
                manual_price=manual_price,
            )
            session.add(item)
            session.flush()
            seen_addons: set[int] = set()
            item_total = product_total
            for addon_input in item_input.addons:
                if addon_input.addon_id in seen_addons:
                    raise ServiceError(400, "duplicate_addon", "An add-on can appear only once per order item")
                seen_addons.add(addon_input.addon_id)
                addon, addon_price, addon_manual_price = _addon_price(session, product, addon_input)
                addon_total = _integer_money(addon_input.quantity * addon_price, "Add-on subtotal")
                session.add(OrderItemAddOn(
                    order_item_id=item.id,
                    addon_id=addon.id,
                    quantity=addon_input.quantity,
                    unit_price=addon_price,
                    total_price=addon_total,
                    price_option_id=None,
                    manual_price=addon_manual_price,
                ))
                item_total += addon_total
            item.total_price = item_total
            total += item_total
        order.total_amount = total
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise conflict("Could not create order") from exc
    except Exception:
        session.rollback()
        raise
    return get_order(session, order.id)


def get_order(session: Session, order_id: int) -> Order:
    order = session.scalars(_order_query().where(Order.id == order_id)).one_or_none()
    if order is None:
        raise not_found("Order")
    return order


def list_orders(
    session: Session,
    business_date: date | None,
    payment_status: PaymentStatus | None,
    order_type: OrderType | None,
    delivery_worker_id: int | None,
    limit: int,
    offset: int,
) -> Sequence[Order]:
    query = _order_query().join(BusinessDay).order_by(Order.id.desc()).limit(limit).offset(offset)
    if business_date is not None:
        query = query.where(BusinessDay.business_date == business_date)
    if payment_status is not None:
        query = query.where(Order.payment_status == payment_status)
    if order_type is not None:
        query = query.where(Order.order_type == order_type)
    if delivery_worker_id is not None:
        query = query.where(Order.delivery_worker_id == delivery_worker_id)
    return session.scalars(query).all()
