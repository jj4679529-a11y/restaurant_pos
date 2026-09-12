from app.models import Order, OrderType


def _money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so‘m"


def _quantity(quantity) -> str:
    return format(quantity, "f")


def build_receipt(order: Order, restaurant_name: str) -> str:
    """Render a UTF-8 plain-text receipt from immutable order snapshots."""
    receipt_time = order.paid_at or order.created_at
    lines = [
        restaurant_name,
        "=" * 32,
        f"Chek #{order.order_number}",
        f"Vaqt: {receipt_time.strftime('%Y-%m-%d %H:%M')}",
        f"Tur: {'Choykhona' if order.order_type is OrderType.CHAYKHANA else 'Delivery'}",
    ]
    if order.order_type is OrderType.DELIVERY and order.delivery_worker is not None:
        lines.append(f"Yetkazib beruvchi: {order.delivery_worker.name}")
    lines.append("-" * 32)
    for item in order.items:
        lines.append(f"{item.product.name} x{_quantity(item.quantity)}")
        lines.append(f"  {_money(item.unit_price)} = {_money(item.total_price - sum(addon.total_price for addon in item.addons))}")
        for addon in item.addons:
            lines.append(f"  + {addon.addon.name} x{_quantity(addon.quantity)}")
            lines.append(f"    {_money(addon.unit_price)} = {_money(addon.total_price)}")
        lines.append(f"  Jami: {_money(item.total_price)}")
    lines.extend([
        "=" * 32,
        f"UMUMIY: {_money(order.total_amount)}",
        f"Holat: {order.payment_status.value}",
    ])
    return "\n".join(lines)
