from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any

from app.menu_rules import PIECE_DRINKS, menu_key


def format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so‘m"


def format_quantity(value: Decimal) -> str:
    text = format(Decimal(value), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class CartValidationError(ValueError):
    pass


def _key(value: str) -> str:
    return menu_key(value or "")


def _is_osh(value: str) -> bool:
    key = _key(value)
    return key == "osh" or key.endswith(" osh")


def _is_jizz(value: str) -> bool:
    return _key(value) == "jizz"


def _is_gosht(value: str) -> bool:
    return _key(value) == "gosht"


def _line_total(
    quantity: Decimal,
    unit_price: int,
    label: str,
) -> int:
    try:
        normalized_quantity = Decimal(str(quantity))
        normalized_price = Decimal(unit_price)

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as error:
        raise CartValidationError(
            f"{label} uchun miqdor yoki narx noto‘g‘ri"
        ) from error

    if (
        not normalized_quantity.is_finite()
        or not normalized_price.is_finite()
    ):
        raise CartValidationError(
            f"{label} uchun miqdor yoki narx noto‘g‘ri"
        )

    if normalized_price != normalized_price.to_integral_value():
        raise CartValidationError(
            f"{label} narxi butun so‘m bo‘lishi kerak"
        )

    if normalized_quantity <= 0:
        raise CartValidationError(
            f"{label} miqdori musbat bo‘lishi kerak"
        )

    if normalized_price <= 0:
        raise CartValidationError(
            f"{label} narxi sozlanmagan"
        )

    total = normalized_quantity * normalized_price

    if total != total.to_integral_value():
        raise CartValidationError(
            f"{label} summasi butun so‘m bo‘lishi kerak"
        )

    return int(total)


@dataclass(frozen=True)
class CartAddOn:
    addon_id: int
    name: str
    quantity: Decimal
    unit_price: int
    manual_price: int | None = None

    @property
    def total_price(self) -> int:
        is_gosht = _is_gosht(self.name)

        # Manual addon price is allowed ONLY for Go‘sht.
        if self.manual_price is not None and not is_gosht:
            raise CartValidationError(
                f"{self.name} narxini kassir o‘zgartira olmaydi"
            )

        if is_gosht:
            if (
                self.manual_price is None
                or self.manual_price < 5000
            ):
                raise CartValidationError(
                    "Go‘sht eng kam summasi: 5 000 so‘m"
                )

            if self.unit_price != self.manual_price:
                raise CartValidationError(
                    "Go‘sht narxi noto‘g‘ri"
                )

        return _line_total(
            self.quantity,
            self.unit_price,
            self.name,
        )

    def to_payload(self) -> dict[str, Any]:
        # Validate before producing API payload.
        _ = self.total_price

        payload: dict[str, Any] = {
            "addon_id": self.addon_id,
            "quantity": f"{self.quantity:.3f}",
        }

        if self.manual_price is not None:
            payload["manual_price"] = self.manual_price

        return payload


@dataclass(frozen=True)
class CartItem:
    product_id: int
    name: str
    quantity: Decimal
    unit_price: int
    selected_price_option_id: int | None = None
    manual_price: int | None = None
    addons: tuple[CartAddOn, ...] = ()
    option_name: str | None = None
    unit_type: str | None = None

    @property
    def product_total(self) -> int:
        return _line_total(
            self.quantity,
            self.unit_price,
            self.name,
        )

    @property
    def total_price(self) -> int:
        return self.product_total + sum(
            addon.total_price
            for addon in self.addons
        )

    @classmethod
    def from_catalog(
        cls,
        product: dict[str, Any],
        quantity: Decimal,
        price_option: dict[str, Any] | None = None,
        manual_price: int | None = None,
        addons: tuple[CartAddOn, ...] = (),
    ) -> "CartItem":
        name = str(product["name"])
        key = _key(name)

        is_osh = _is_osh(name)
        is_jizz = _is_jizz(name)

        unit_type = product.get("unit_type")

        # Kompot/Ayron and other final piece-drinks must never
        # return to the old cashier liter-entry flow.
        if key in PIECE_DRINKS and unit_type != "PIECE":
            raise CartValidationError(
                "Admin bu ichimlik uchun dona narxini sozlashi kerak"
            )

        # Manual product pricing is allowed ONLY for Jizz.
        if manual_price is not None and not is_jizz:
            raise CartValidationError(
                f"{name} narxini kassir o‘zgartira olmaydi"
            )

        # All Osh variants require a configured PriceOption.
        if is_osh and price_option is None:
            raise CartValidationError(
                "Osh porsiyasini tanlang"
            )

        if price_option is not None:
            unit_price = int(
                price_option.get("price", 0)
            )

            selected_price_option_id = int(
                price_option["id"]
            )

            if manual_price is not None:
                raise CartValidationError(
                    "Porsiya narxi bilan qo‘lda narx "
                    "birga ishlatilmaydi"
                )

            if unit_price <= 0:
                raise CartValidationError(
                    "Porsiya narxi sozlanmagan"
                )

        elif is_jizz:
            if manual_price is None or manual_price <= 0:
                raise CartValidationError(
                    "Jizz narxini tanlang yoki kiriting"
                )

            unit_price = int(manual_price)
            selected_price_option_id = None

        else:
            # Do not trust a stale allows_manual_price flag.
            # All ordinary products use Admin-configured price.
            unit_price = int(
                product.get("base_price", 0)
            )

            selected_price_option_id = None

            if unit_price <= 0:
                raise CartValidationError(
                    "Mahsulot narxi Administrator "
                    "tomonidan sozlanmagan"
                )

        return cls(
            product_id=int(product["id"]),
            name=name,
            quantity=quantity,
            unit_price=unit_price,
            selected_price_option_id=selected_price_option_id,
            manual_price=manual_price if is_jizz else None,
            addons=addons,
            option_name=(
                str(price_option["name"])
                if price_option
                else None
            ),
            unit_type=unit_type,
        )

    def to_payload(self) -> dict[str, Any]:
        # Prevent invalid/stale cart state reaching API.
        _ = self.total_price

        payload: dict[str, Any] = {
            "product_id": self.product_id,
            "quantity": f"{self.quantity:.3f}",
            "addons": [
                addon.to_payload()
                for addon in self.addons
            ],
        }

        if self.selected_price_option_id is not None:
            payload[
                "selected_price_option_id"
            ] = self.selected_price_option_id

        if self.manual_price is not None:
            if not _is_jizz(self.name):
                raise CartValidationError(
                    f"{self.name} uchun qo‘lda narx mumkin emas"
                )

            payload[
                "manual_price"
            ] = self.manual_price

        return payload


@dataclass
class Cart:
    items: list[CartItem] = field(
        default_factory=list
    )

    @property
    def total_amount(self) -> int:
        return sum(
            item.total_price
            for item in self.items
        )

    def add(self, item: CartItem) -> None:
        _ = item.total_price
        self.items.append(item)

    def remove(self, index: int) -> None:
        del self.items[index]

    def replace(
        self,
        index: int,
        item: CartItem,
    ) -> None:
        _ = item.total_price
        self.items[index] = item

    def change_quantity(
        self,
        index: int,
        delta: int,
    ) -> None:
        item = self.items[index]

        new_quantity = (
            item.quantity + Decimal(delta)
        )

        if new_quantity <= 0:
            self.remove(index)
            return

        # Addon quantity is an independent total for the line.
        self.replace(
            index,
            replace(
                item,
                quantity=new_quantity,
            ),
        )

    def clear(self) -> None:
        self.items.clear()

    def order_payload(
        self,
        order_type: str,
        delivery_worker_id: int | None = None,
    ) -> dict[str, Any]:
        if not self.items:
            raise CartValidationError(
                "Savat bo‘sh"
            )

        if (
            order_type == "DELIVERY"
            and delivery_worker_id is None
        ):
            raise CartValidationError(
                "Yetkazib beruvchini tanlang"
            )

        if (
            order_type == "CHAYKHANA"
            and delivery_worker_id is not None
        ):
            raise CartValidationError(
                "Choyxona buyurtmasiga "
                "yetkazib beruvchi biriktirilmaydi"
            )

        if order_type not in {
            "CHAYKHANA",
            "DELIVERY",
        }:
            raise CartValidationError(
                "Buyurtma turi noto‘g‘ri"
            )

        payload: dict[str, Any] = {
            "order_type": order_type,
            "items": [
                item.to_payload()
                for item in self.items
            ],
        }

        if delivery_worker_id is not None:
            payload[
                "delivery_worker_id"
            ] = delivery_worker_id

        return payload


@dataclass
class SessionState:
    access_token: str
    user: dict[str, Any]

    def clear(self) -> None:
        self.access_token = ""
        self.user = {}


def decimal_quantity(
    value: float,
) -> Decimal:
    try:
        return Decimal(
            str(value)
        ).quantize(
            Decimal("0.001")
        )

    except (
        InvalidOperation,
        ValueError,
    ) as error:
        raise CartValidationError(
            "Miqdor noto‘g‘ri"
        ) from error
