from decimal import Decimal

import pytest

from app.ui.api_client import ApiError, PosApiClient
from app.ui.checkout import pay_and_print
from app.ui.state import Cart, CartAddOn, CartItem, CartValidationError, SessionState


OSH = {
    "id": 185,
    "name": "Osh",
    "base_price": 0,
    "allows_manual_price": False,
    "price_options": [
        {"id": 91, "name": "15000", "price": 15_000, "is_active": True},
    ],
}
GOSHT = {
    "id": 68,
    "name": "Go‘sht",
    "base_price": 0,
    "allows_manual_price": True,
}


def test_osh_price_option_and_manual_gosht_build_existing_order_payload() -> None:
    gosht = CartAddOn(
        addon_id=GOSHT["id"],
        name=GOSHT["name"],
        quantity=Decimal("1.000"),
        unit_price=15_000,
        manual_price=15_000,
    )
    item = CartItem.from_catalog(
        OSH,
        Decimal("1.000"),
        price_option=OSH["price_options"][0],
        addons=(gosht,),
    )
    cart = Cart([item])

    assert item.selected_price_option_id == 91
    assert item.total_price == 30_000
    assert cart.total_amount == 30_000
    assert cart.order_payload("CHAYKHANA") == {
        "order_type": "CHAYKHANA",
        "items": [{
            "product_id": 185,
            "quantity": "1.000",
            "selected_price_option_id": 91,
            "addons": [{"addon_id": 68, "quantity": "1.000", "manual_price": 15_000}],
        }],
    }


@pytest.mark.parametrize(
    ("quantity", "expected_total"),
    [
        (Decimal("1"), 2_000),
        (Decimal("1.000"), 2_000),
        (Decimal("0.5"), 1_000),
    ],
)
def test_decimal_addon_quantities_with_integer_uzs_price_are_valid(
    quantity: Decimal,
    expected_total: int,
) -> None:
    tuxum = CartAddOn(
        addon_id=10,
        name="Tuxum 1",
        quantity=quantity,
        unit_price=2_000,
    )
    osh = CartItem.from_catalog(
        OSH,
        Decimal("0.5"),
        price_option=OSH["price_options"][0],
        addons=(tuxum,),
    )
    cart = Cart()
    cart.add(osh)

    assert tuxum.total_price == expected_total
    assert osh.product_total == 7_500
    assert cart.total_amount == 7_500 + expected_total


def test_unconfigured_addon_price_is_rejected_before_cart_mutation() -> None:
    unconfigured = CartAddOn(addon_id=10, name="Tuxum 1", quantity=Decimal("1.000"), unit_price=0)
    item = CartItem.from_catalog(OSH, Decimal("1.000"), price_option=OSH["price_options"][0], addons=(unconfigured,))
    cart = Cart()

    with pytest.raises(CartValidationError, match="narxi sozlanmagan"):
        cart.add(item)
    assert cart.items == []


def test_delivery_requires_worker_and_chaykhana_rejects_worker() -> None:
    item = CartItem.from_catalog(OSH, Decimal("1.000"), price_option=OSH["price_options"][0])
    cart = Cart([item])

    with pytest.raises(CartValidationError, match="Yetkazib beruvchini"):
        cart.order_payload("DELIVERY")
    with pytest.raises(CartValidationError, match="Choyxona"):
        cart.order_payload("CHAYKHANA", delivery_worker_id=3)
    assert cart.order_payload("DELIVERY", delivery_worker_id=3)["delivery_worker_id"] == 3


class CheckoutClient:
    def __init__(self, print_error: ApiError | None = None) -> None:
        self.print_error = print_error
        self.paid_orders: list[int] = []
        self.printed_orders: list[tuple[int, int]] = []

    def pay_order(self, order_id: int):
        self.paid_orders.append(order_id)
        return {"order_id": order_id, "payment_status": "PAID"}

    def print_order(self, order_id: int, printer_id: int):
        self.printed_orders.append((order_id, printer_id))
        if self.print_error is not None:
            raise self.print_error
        return {"order_id": order_id, "status": "SUCCESS"}


def test_payment_success_print_failure_preserves_paid_outcome() -> None:
    client = CheckoutClient(ApiError(500, "PRINTER_ERROR", "Printer offline"))

    outcome = pay_and_print(client, 42, 77)  # type: ignore[arg-type]

    assert client.paid_orders == [42]
    assert client.printed_orders == [(42, 77)]
    assert outcome.payment["payment_status"] == "PAID"
    assert outcome.printed is False
    assert outcome.print_error == "Printer offline"


def test_payment_success_without_printer_is_not_reversed_and_logout_clears_session() -> None:
    client = CheckoutClient()
    outcome = pay_and_print(client, 43, None)  # type: ignore[arg-type]
    session = SessionState(access_token="runtime-token", user={"id": 7})

    assert client.paid_orders == [43]
    assert client.printed_orders == []
    assert outcome.printer_configured is False
    assert outcome.payment["payment_status"] == "PAID"
    session.clear()
    assert session.access_token == ""
    assert session.user == {}


def test_api_client_logout_clears_only_runtime_token() -> None:
    client = PosApiClient("http://pos.local:8000", transport=lambda _request, _timeout: None)  # type: ignore[arg-type]
    client.set_access_token("runtime-token")
    client.clear_session()
    assert client.access_token is None
