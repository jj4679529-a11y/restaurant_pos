from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

# Current Windows Generic/Text Only printer is safest around 32 chars.
# After physical testing we can raise this to 36/42 if the printer supports it.
WIDTH = 32

DEFAULT_RESTAURANT_NAME = "Komronbek Zig'ir oshi"


def _money(value: Any) -> str:
    amount = int(Decimal(str(value or 0)))
    return f"{amount:,}".replace(",", " ") + " so‘m"


def _qty(value: Any) -> str:
    text = format(Decimal(str(value or 0)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _safe_text(value: Any) -> str:
    return (
        str(value)
        .replace("‘", "'")
        .replace("’", "'")
        .replace("ʻ", "'")
        .replace("ʼ", "'")
    )


def _center(text: str) -> str:
    return _safe_text(text)[:WIDTH].center(WIDTH)


def _separator(char: str = "-") -> str:
    return char * WIDTH


def _left_right(left: str, right: str) -> str:
    left = str(left)
    right = str(right)

    available = WIDTH - len(right) - 1
    if available < 1:
        return right[-WIDTH:]

    return f"{left[:available]:<{available}} {right}"


def _wrap(text: str, width: int = WIDTH) -> list[str]:
    text = " ".join(str(text).split())

    if not text:
        return [""]

    words = text.split(" ")
    rows: list[str] = []
    current = ""

    for word in words:
        candidate = word if not current else f"{current} {word}"

        if len(candidate) <= width:
            current = candidate
            continue

        if current:
            rows.append(current)

        while len(word) > width:
            rows.append(word[:width])
            word = word[width:]

        current = word

    if current:
        rows.append(current)

    return rows


def _item_name(item: Any) -> str:
    product = getattr(item, "product", None)

    return _safe_text(
        getattr(product, "name", None)
        or getattr(item, "name", None)
        or getattr(item, "product_name", None)
        or "Mahsulot"
    )


def _item_quantity(item: Any) -> Any:
    return getattr(item, "quantity", None) or 1


def _item_unit_price(item: Any) -> Any:
    return (
        getattr(item, "unit_price", None)
        or getattr(item, "price", None)
        or 0
    )


def _item_total(item: Any) -> Any:
    return (
        getattr(item, "total_price", None)
        or getattr(item, "line_total", None)
        or getattr(item, "total_amount", None)
        or 0
    )


def _item_addons(item: Any) -> list[Any]:
    return list(
        getattr(item, "addons", None)
        or getattr(item, "order_item_addons", None)
        or []
    )


def _addon_name(row: Any) -> str:
    addon = getattr(row, "addon", None)

    return _safe_text(
        getattr(addon, "name", None)
        or getattr(row, "name", None)
        or "Qo'shimcha"
    )


def _addon_quantity(row: Any) -> Any:
    return getattr(row, "quantity", None) or 1


def _addon_unit_price(row: Any) -> Any:
    return (
        getattr(row, "unit_price", None)
        or getattr(row, "price", None)
        or 0
    )


def _addon_total(row: Any) -> Any:
    return (
        getattr(row, "total_price", None)
        or getattr(row, "line_total", None)
        or getattr(row, "total_amount", None)
        or 0
    )


def _order_type(order: Any) -> str:
    raw = getattr(order, "order_type", None)
    value = getattr(raw, "value", raw)
    value = str(value or "").upper()

    if value == "CHAYKHANA":
        return "Choyxona"

    if value == "DELIVERY":
        return "Yetkazib berish"

    if value in {"TAKEAWAY", "TAKE_AWAY"}:
        return "Olib ketish"

    return value.title() or "-"


def _order_number(order: Any) -> str:
    number = getattr(order, "order_number", None)

    if number:
        return str(number)

    order_id = getattr(order, "id", None)
    return str(order_id or "-")


def build_strict_receipt(
    order: Any,
    restaurant_name: str | None = None,
) -> str:
    restaurant_name = (
        str(restaurant_name or "").strip()
        or DEFAULT_RESTAURANT_NAME
    )

    receipt_time = (
        getattr(order, "paid_at", None)
        or getattr(order, "created_at", None)
        or datetime.now()
    )

    if hasattr(receipt_time, "strftime"):
        time_text = receipt_time.strftime("%d.%m.%Y %H:%M")
    else:
        time_text = str(receipt_time)

    items = list(
        getattr(order, "items", None)
        or getattr(order, "order_items", None)
        or []
    )

    total = int(
        Decimal(
            str(
                getattr(order, "total_amount", None)
                or sum(
                    int(Decimal(str(_item_total(item))))
                    for item in items
                )
            )
        )
    )

    lines: list[str] = [
        _separator("="),
        _center(restaurant_name.upper()),
        _center("ZIG'IR OSHI"),
        _separator("="),
        _left_right("Chek", f"#{_order_number(order)}"),
        f"Vaqt: {time_text}",
        f"Tur:  {_order_type(order)}",
    ]

    worker = getattr(order, "delivery_worker", None)
    if worker is not None:
        worker_name = getattr(worker, "name", None)
        if worker_name:
            lines.append(f"Yetkazib beruvchi: {_safe_text(worker_name)}")

    lines.extend([
        _separator("-"),
        "MAHSULOTLAR",
        _separator("-"),
    ])

    for index, item in enumerate(items, start=1):
        name = _item_name(item)
        qty = _qty(_item_quantity(item))
        unit_price = _money(_item_unit_price(item))
        item_total = _money(_item_total(item))

        name_lines = _wrap(f"{index}. {name}")

        lines.extend(name_lines)

        price_text = f"{qty} x {unit_price}"
        lines.append(_left_right(price_text, item_total))

        for addon in _item_addons(item):
            addon_name = _addon_name(addon)
            addon_qty = _qty(_addon_quantity(addon))
            addon_price = _money(_addon_unit_price(addon))
            addon_total = _money(_addon_total(addon))

            addon_lines = _wrap(f"   + {addon_name}")
            lines.extend(addon_lines)

            addon_price_text = f"   {addon_qty} x {addon_price}"
            lines.append(
                _left_right(
                    addon_price_text,
                    addon_total,
                )
            )

        lines.append("")

    if lines and lines[-1] == "":
        lines.pop()

    lines.extend([
        _separator("="),
        _left_right("UMUMIY:", _money(total)),
        _separator("="),
        "Holat: PAID",
        "",
        _center("RAHMAT!"),
        _center("YANA TASHRIF BUYURING!"),
        "",
    ])

    return "\n".join(lines)
