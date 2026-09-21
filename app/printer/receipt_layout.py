from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

# Generic / Text Only printer uchun xavfsiz kenglik.
# Har bir fizik satr 32 belgidan oshmaydi.
WIDTH = 32

DEFAULT_RESTAURANT_NAME = "Komronbek Zig'ir oshi"


def _ascii(value: Any) -> str:
    """Windows Generic/Text Only uchun xavfsiz Uzbek matn."""
    text = str(value or "")

    replacements = {
        "‘": "'",
        "’": "'",
        "ʻ": "'",
        "ʼ": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "\u00a0": " ",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


def _amount(value: Any) -> str:
    amount = int(Decimal(str(value or 0)))
    return f"{amount:,}".replace(",", " ")


def _money(value: Any) -> str:
    return _amount(value) + " so‘m"


def _qty(value: Any) -> str:
    text = format(Decimal(str(value or 0)), "f")

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text or "0"


def _center(value: Any) -> str:
    text = _ascii(value)[:WIDTH]
    return text.center(WIDTH)


def _separator(char: str = "-") -> str:
    return char * WIDTH


def _left_right(left: Any, right: Any) -> str:
    left = _ascii(left)

    # Pul formatidagi Uzbek "so‘m" yozuvini saqlaymiz.
    # Mahsulot nomlari alohida _ascii() orqali normalize qilinadi.
    right = " ".join(str(right or "").split())

    if len(right) >= WIDTH:
        return right[-WIDTH:]

    available = WIDTH - len(right) - 1

    if available < 1:
        return right[-WIDTH:]

    left = left[:available]

    return left + (" " * (WIDTH - len(left) - len(right))) + right


def _wrap(value: Any, width: int = WIDTH) -> list[str]:
    text = _ascii(value)

    if not text:
        return [""]

    words = text.split()
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


def _items(order: Any) -> list[Any]:
    return list(
        getattr(order, "items", None)
        or getattr(order, "order_items", None)
        or []
    )


def _item_name(item: Any) -> str:
    product = getattr(item, "product", None)

    return _ascii(
        getattr(product, "name", None)
        or getattr(item, "name", None)
        or getattr(item, "product_name", None)
        or "Mahsulot"
    )


def _item_qty(item: Any) -> Any:
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


def _addons(item: Any) -> list[Any]:
    return list(
        getattr(item, "addons", None)
        or getattr(item, "order_item_addons", None)
        or []
    )


def _addon_name(row: Any) -> str:
    addon = getattr(row, "addon", None)

    return _ascii(
        getattr(addon, "name", None)
        or getattr(row, "name", None)
        or "Qo'shimcha"
    )


def _addon_qty(row: Any) -> Any:
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

    return _ascii(value.title() or "-")


def _order_number(order: Any) -> str:
    number = getattr(order, "order_number", None)

    if number:
        return str(number)

    return str(getattr(order, "id", None) or "-")


def build_strict_receipt(
    order: Any,
    restaurant_name: str | None = None,
) -> str:
    restaurant_name = (
        _ascii(restaurant_name).strip()
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
        time_text = _ascii(receipt_time)

    items = _items(order)

    total = getattr(order, "total_amount", None)

    if total is None:
        total = sum(
            int(Decimal(str(_item_total(item) or 0)))
            for item in items
        )

    total = int(Decimal(str(total or 0)))

    lines: list[str] = [
        _separator("="),
        _center(restaurant_name),
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
            lines.extend(
                _wrap(
                    f"Yetkazib beruvchi: "
                    f"{_ascii(worker_name)}"
                )
            )

    lines.extend([
        _separator("-"),
        "MAHSULOTLAR",
        _separator("-"),
    ])

    for index, item in enumerate(items, start=1):
        name = _item_name(item)

        # 1. Mahsulot nomi
        name_rows = _wrap(f"{index}. {name}")

        for row in name_rows:
            lines.append(row)

        # 1 x 15 000          15 000
        qty_price = (
            f"{_qty(_item_qty(item))}"
            f" x {_amount(_item_unit_price(item))}"
        )

        lines.append(
            _left_right(
                qty_price,
                _money(_item_total(item)),
            )
        )

        for addon in _addons(item):
            addon_name = _addon_name(addon)

            for row in _wrap(f"  + {addon_name}"):
                lines.append(row)

            addon_qty_price = (
                f"  {_qty(_addon_qty(addon))}"
                f" x {_amount(_addon_unit_price(addon))}"
            )

            lines.append(
                _left_right(
                    addon_qty_price,
                    _money(_addon_total(addon)),
                )
            )

        # Mahsulotlar orasida bo'sh satr emas,
        # faqat yengil separator.
        if index != len(items):
            lines.append("-" * 10)

    lines.extend([
        _separator("="),
        _left_right("UMUMIY:", _money(total)),
        _separator("="),
        "To'lov: TO'LANGAN",
        "Holat: PAID",
        "",
        _center("RAHMAT!"),
        _center("YANA TASHRIF BUYURING!"),
        "",
    ])

    # Hech qaysi satr WIDTH dan oshmasligini kafolatlaymiz.
    safe_lines: list[str] = []

    for line in lines:
        if len(line) <= WIDTH:
            safe_lines.append(line)
        else:
            safe_lines.extend(_wrap(line))

    return "\n".join(safe_lines)
