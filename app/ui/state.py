from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any


def format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so‘m"


class CartValidationError(ValueError):
    pass


def _line_total(quantity: Decimal, unit_price: int, label: str) -> int:
    try:
        normalized_quantity = Decimal(str(quantity))
        normalized_price = Decimal(unit_price)
    except (InvalidOperation, TypeError, ValueError) as error:
        raise CartValidationError(f"{label} uchun miqdor yoki narx noto‘g‘ri") from error
    if not normalized_quantity.is_finite() or not normalized_price.is_finite():
        raise CartValidationError(f"{label} uchun miqdor yoki narx noto‘g‘ri")
    if normalized_price != normalized_price.to_integral_value():
        raise CartValidationError(f"{label} narxi butun so‘m bo‘lishi kerak")
    if normalized_quantity <= 0:
        raise CartValidationError(f"{label} miqdori musbat bo‘lishi kerak")
    if normalized_price <= 0:
        raise CartValidationError(f"{label} narxi sozlanmagan")
    total = normalized_quantity * normalized_price
    if total != total.to_integral_value():
        raise CartValidationError(f"{label} summasi butun so‘m bo‘lishi kerak")
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
        return _line_total(self.quantity, self.unit_price, self.name)

    def to_payload(self) -> dict[str, Any]:
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

    @property
    def product_total(self) -> int:
        return _line_total(self.quantity, self.unit_price, self.name)

    @property
    def total_price(self) -> int:
        return self.product_total + sum(addon.total_price for addon in self.addons)

    @classmethod
    def from_catalog(
        cls,
        product: dict[str, Any],
        quantity: Decimal,
        price_option: dict[str, Any] | None = None,
        manual_price: int | None = None,
        addons: tuple[CartAddOn, ...] = (),
    ) -> "CartItem":
        if price_option is not None:
            unit_price = int(price_option["price"])
            selected_price_option_id = int(price_option["id"])
            if manual_price is not None:
                raise CartValidationError("PriceOption bilan qo‘lda narx birga ishlatilmaydi")
        elif bool(product.get("allows_manual_price")):
            if manual_price is None or manual_price <= 0:
                raise CartValidationError("Bu mahsulot uchun qo‘lda narx kiriting")
            unit_price = manual_price
            selected_price_option_id = None
        else:
            unit_price = int(product.get("base_price", 0))
            selected_price_option_id = None
            if unit_price <= 0:
                raise CartValidationError("Mahsulot uchun PriceOption tanlang")
        return cls(
            product_id=int(product["id"]),
            name=str(product["name"]),
            quantity=quantity,
            unit_price=unit_price,
            selected_price_option_id=selected_price_option_id,
            manual_price=manual_price,
            addons=addons,
            option_name=str(price_option["name"]) if price_option else None,
        )

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "product_id": self.product_id,
            "quantity": f"{self.quantity:.3f}",
            "addons": [addon.to_payload() for addon in self.addons],
        }
        if self.selected_price_option_id is not None:
            payload["selected_price_option_id"] = self.selected_price_option_id
        if self.manual_price is not None:
            payload["manual_price"] = self.manual_price
        return payload


@dataclass
class Cart:
    items: list[CartItem] = field(default_factory=list)

    @property
    def total_amount(self) -> int:
        return sum(item.total_price for item in self.items)

    def add(self, item: CartItem) -> None:
        # Validate before mutation so an invalid catalog price can never leave
        # the touchscreen cart in a state that crashes while rendering.
        _ = item.total_price
        self.items.append(item)

    def remove(self, index: int) -> None:
        del self.items[index]

    def replace(self, index: int, item: CartItem) -> None:
        _ = item.total_price
        self.items[index] = item

    def change_quantity(self, index: int, delta: int) -> None:
        item = self.items[index]
        new_quantity = item.quantity + Decimal(delta)
        if new_quantity <= 0:
            self.remove(index)
            return
        # Addon quantities are totals for this line (also in the API and dialog),
        # not ratios per portion. Changing Osh count must not create fractional eggs.
        self.replace(index, replace(item, quantity=new_quantity))

    def clear(self) -> None:
        self.items.clear()

    def order_payload(self, order_type: str, delivery_worker_id: int | None = None) -> dict[str, Any]:
        if not self.items:
            raise CartValidationError("Savat bo‘sh")
        if order_type == "DELIVERY" and delivery_worker_id is None:
            raise CartValidationError("Yetkazib beruvchini tanlang")
        if order_type == "CHAYKHANA" and delivery_worker_id is not None:
            raise CartValidationError("Choyxona buyurtmasiga yetkazib beruvchi biriktirilmaydi")
        if order_type not in {"CHAYKHANA", "DELIVERY"}:
            raise CartValidationError("Buyurtma turi noto‘g‘ri")
        payload: dict[str, Any] = {
            "order_type": order_type,
            "items": [item.to_payload() for item in self.items],
        }
        if delivery_worker_id is not None:
            payload["delivery_worker_id"] = delivery_worker_id
        return payload


@dataclass
class SessionState:
    access_token: str
    user: dict[str, Any]

    def clear(self) -> None:
        self.access_token = ""
        self.user = {}


def decimal_quantity(value: float) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError) as error:
        raise CartValidationError("Miqdor noto‘g‘ri") from error
