from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

WIDTH = 42

COMPANY_NAME = 'OOO "MAK FOOD SERVIS"'
BRANCH_NAME = "035-TЦ Экобазар"
ADDRESS_LINE_1 = "г. Ташкент, Мирзо Улугбекский район"
ADDRESS_LINE_2 = 'ул. Т. Малик, дом (ТЦ "ATLAS CHIMGAN")'
TAX_ID = "STIR 301422146"
TITLE = "SOTUV CHEKI"


def _center(text: str) -> str:
    return str(text).center(WIDTH)


def _money(value: Any) -> str:
    amount = int(Decimal(str(value or 0)))
    return f"{amount:,}".replace(",", " ") + ",00"


def _qty(value: Any) -> str:
    text = format(Decimal(str(value or 0)), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _line(left: str = "", right: str = "") -> str:
    left = str(left)
    right = str(right)
    space = WIDTH - len(left) - len(right)
    if space < 1:
        return left[: max(0, WIDTH - len(right) - 1)] + " " + right
    return left + (" " * space) + right


def _row(name: str, qty: str, total: str) -> list[str]:
    name = str(name)
    qty = str(qty)
    total = str(total)

    rows: list[str] = []
    first = name[:22]
    rows.append(f"{first:<22}{qty:>6}{total:>14}")

    rest = name[22:]
    while rest:
        rows.append(rest[:WIDTH])
        rest = rest[WIDTH:]

    return rows


def _get_items(order: Any) -> list[Any]:
    return list(
        getattr(order, "items", None)
        or getattr(order, "order_items", None)
        or []
    )


def _item_name(item: Any) -> str:
    product = getattr(item, "product", None)
    return (
        getattr(product, "name", None)
        or getattr(item, "name", None)
        or getattr(item, "product_name", None)
        or "Mahsulot"
    )


def _item_qty(item: Any) -> Any:
    return getattr(item, "quantity", None) or 1


def _item_total(item: Any) -> Any:
    return (
        getattr(item, "line_total", None)
        or getattr(item, "total_price", None)
        or getattr(item, "total_amount", None)
        or 0
    )


def _item_addons(item: Any) -> list[Any]:
    return list(
        getattr(item, "addons", None)
        or getattr(item, "order_item_addons", None)
        or []
    )


def _addon_name(addon: Any) -> str:
    addon_obj = getattr(addon, "addon", None)
    return (
        getattr(addon_obj, "name", None)
        or getattr(addon, "name", None)
        or "Qo‘shimcha"
    )


def _addon_qty(addon: Any) -> Any:
    return getattr(addon, "quantity", None) or 1


def _addon_total(addon: Any) -> Any:
    return (
        getattr(addon, "line_total", None)
        or getattr(addon, "total_price", None)
        or getattr(addon, "total_amount", None)
        or 0
    )


def _payments(order: Any) -> list[Any]:
    return list(getattr(order, "payments", None) or [])


def _payment_label(payment: Any) -> str:
    raw = (
        getattr(payment, "method", None)
        or getattr(payment, "payment_method", None)
        or getattr(payment, "payment_type", None)
        or "To‘lov"
    )
    text = str(raw).replace("_", " ").strip()
    if text.upper() == "CARD":
        return "UzCard"
    if text.upper() == "CASH":
        return "Naqd"
    return text


def _payment_amount(payment: Any, default_total: int) -> int:
    return int(
        Decimal(
            str(
                getattr(payment, "amount", None)
                or getattr(payment, "paid_amount", None)
                or default_total
            )
        )
    )


def build_strict_receipt(order: Any) -> str:
    created = (
        getattr(order, "paid_at", None)
        or getattr(order, "created_at", None)
        or datetime.now()
    )

    if hasattr(created, "strftime"):
        created_text = created.strftime("%d.%m.%Y %H:%M")
    else:
        created_text = str(created)

    order_id = getattr(order, "id", None) or "—"
    items = _get_items(order)

    total = getattr(order, "total_amount", None)
    if total is None:
        total = sum(
            int(Decimal(str(_item_total(item) or 0)))
            for item in items
        )
    total = int(Decimal(str(total or 0)))

    lines: list[str] = [
        _center(COMPANY_NAME),
        _center(BRANCH_NAME),
        _center(ADDRESS_LINE_1),
        _center(ADDRESS_LINE_2),
        "",
        _center(TITLE),
        "",
        _center(f"Buyurtma # {order_id}"),
        "",
        TAX_ID,
        _line("Buyurtma vaqti", created_text),
        "-" * WIDTH,
        f"{'Mahsulot':<22}{'Miqdori':>6}{'Summa':>14}",
        "-" * WIDTH,
    ]

    for item in items:
        item_name = _item_name(item)
        item_qty = _qty(_item_qty(item))
        item_total = _money(_item_total(item))

        lines.extend(_row(item_name, item_qty, item_total))

        for addon in _item_addons(item):
            addon_name = "+ " + _addon_name(addon)
            addon_qty = _qty(_addon_qty(addon))
            addon_total = _money(_addon_total(addon))
            lines.extend(_row(addon_name, addon_qty, addon_total))

    lines.extend(
        [
            "-" * WIDTH,
            _line("JAMI SUMMA", _money(total)),
            _line("To‘lovga", _money(total)),
            _line("JAMI TO‘LANDI", _money(total)),
            "",
            "Buyurtma to‘lovlari",
        ]
    )

    payments = _payments(order)
    if payments:
        for payment in payments:
            lines.append(
                _line(
                    "- " + _payment_label(payment),
                    _money(_payment_amount(payment, total)),
                )
            )
    else:
        lines.append(_line("- To‘lov", _money(total)))

    lines.extend(
        [
            "",
            _center("RAHMAT!"),
            "",
        ]
    )

    return "\n".join(lines)
