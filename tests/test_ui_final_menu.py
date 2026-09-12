"""Actual Qt widgets exercised offscreen; no restaurant orders are created."""
import os
from decimal import Decimal
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.ui.api_client import ApiConnectionError
from app.ui.checkout import pay_and_print, print_paid_order
from app.ui.config import UiSettings
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.main_window import PosMainWindow
from app.ui.state import Cart, CartItem, SessionState
from app.ui.widgets.product_card import product_pixmap, ProductCard


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def osh():
    return {
        "id": 501, "category_id": 21, "name": "Osh", "base_price": 0,
        "allows_manual_price": False,
        "price_options": [
            {"id": 71, "name": "0.5 porsiya", "quantity": "0.500", "price": 17000},
            {"id": 72, "name": "1 porsiya", "quantity": "1.000", "price": 31000},
            {"id": 73, "name": "Old", "quantity": "1", "price": 5000, "is_active": False},
        ],
        "available_addons": [
            {"id": 41, "name": "Tuxum 1", "base_price": 3000},
            {"id": 42, "name": "Tuxum 2", "base_price": 5000},
            {"id": 43, "name": "Qazi", "base_price": 8000},
            {"id": 44, "name": "Go'sht", "base_price": 0, "allows_manual_price": True,
             "manual_price_presets": [{"amount": 15000, "is_active": True}]},
        ],
    }


@pytest.mark.parametrize("index,price", [(0, 17000), (1, 31000)])
def test_osh_exact_configured_portion_price(qt_app, osh, index, price):
    dialog = ProductDialog(osh)
    assert not dialog.confirm.isEnabled()
    assert len(dialog.options_group.buttons()) == 2
    dialog.options_group.buttons()[index].click()
    item = dialog._item()
    assert item.total_price == price
    # One selected half-portion costs the exact half-portion price, not half again.
    assert item.to_payload()["quantity"] == "1.000"
    assert item.to_payload()["selected_price_option_id"] == osh["price_options"][index]["id"]
    assert "manual_price" not in item.to_payload()
    dialog.close()


def test_admin_price_change_is_loaded_dynamically(qt_app, osh):
    osh["price_options"][0]["price"] = 19500
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    assert dialog._item().unit_price == 19500
    assert "19 500" in dialog.total.text()
    dialog.close()


def test_egg_types_and_qazi_piece_quantities(qt_app, osh):
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    for addon in osh["available_addons"][:3]:
        dialog._addon_count(addon, 1)
        dialog._addon_count(addon, 1)
    assert [a.total_price for a in dialog._item().addons] == [6000, 10000, 16000]
    assert dialog._item().total_price == 49000
    dialog._addon_count(osh["available_addons"][0], -1)
    assert dialog._item().total_price == 46000
    dialog.close()


@pytest.mark.parametrize("target,amount", [("gosht", 15000), ("gosht", 17300), ("jizz", 70000), ("jizz", 73400)])
def test_manual_presets_and_custom_snapshots(qt_app, osh, monkeypatch, target, amount):
    picker = Mock(return_value=amount)
    monkeypatch.setattr(NumberDialog, "money", picker)
    if target == "gosht":
        dialog = ProductDialog(osh)
        dialog.options_group.buttons()[0].click()
        dialog._manual_addon(osh["available_addons"][3])
        item = dialog._item().addons[0]
        assert picker.call_args.args[2] == osh["available_addons"][3]["manual_price_presets"]
        assert "selected_price_option_id" not in item.to_payload()
    else:
        product = {"id": 600, "name": "Jizz", "allows_manual_price": True,
                   "manual_price_presets": [{"amount": 70000}]}
        dialog = ProductDialog(product)
        dialog._product_price()
        item = dialog._item()
        assert picker.call_args.args[2] == product["manual_price_presets"]
    assert item.manual_price == item.unit_price == item.total_price == amount
    assert item.to_payload()["manual_price"] == amount
    dialog.close()


def test_keypad_preset_custom_clear_backspace_and_positive_only(qt_app):
    dialog = NumberDialog(presets=[{"amount": 15000}, {"amount": 90000, "is_active": False}])
    assert not dialog.confirm.isEnabled()
    preset = next(b for b in dialog.findChildren(QPushButton) if b.text() == "15 000 so‘m")
    preset.click()
    assert dialog.amount == 15000
    assert not any("90 000" in b.text() for b in dialog.findChildren(QPushButton))
    dialog._press("C")
    for digit in "173001":
        dialog._press(digit)
    dialog._press("⌫")
    assert dialog.amount == 17300
    assert dialog.display.text() == "17 300 so‘m"
    dialog._press("C")
    dialog.accept()
    assert dialog.result() == 0
    dialog.close()


def test_cart_edit_counts_and_remove_keep_line_addon_counts(qt_app, osh):
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    dialog._addon_count(osh["available_addons"][0], 1)
    cart = Cart()
    cart.add(dialog._item())
    cart.change_quantity(0, 1)
    cart.change_quantity(0, 1)
    cart.change_quantity(0, -1)
    assert cart.items[0].quantity == 2
    assert cart.items[0].addons[0].quantity == 1
    assert cart.total_amount == 37000
    edit = ProductDialog(osh, cart.items[0])
    edit.options_group.buttons()[1].click()
    cart.replace(0, edit._item())
    assert cart.total_amount == 65000
    cart.remove(0)
    assert cart.total_amount == 0
    edit.close()
    dialog.close()


def test_local_images_and_placeholder(qt_app, osh):
    missing = product_pixmap()
    broken = product_pixmap(b"not an image")
    assert not missing.isNull()
    assert missing.toImage() == broken.toImage()
    source = QPixmap(20, 20)
    source.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    source.save(buffer, "PNG")
    loaded = product_pixmap(bytes(buffer.data()))
    assert loaded.toImage().pixelColor(0, 0) == QColor("red")
    card = ProductCard(osh)
    assert "Osh" in card.text() and not card.icon().isNull()
    card.close()


@pytest.fixture
def window(qt_app, monkeypatch):
    for method in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, method, Mock())
    client = Mock()
    client.load_catalog.return_value = ([], [], [{"id": 99, "name": "Ali"}])
    client.create_order.return_value = {"id": 800, "order_number": "00800", "payment_status": "PENDING", "total_amount": 12000}
    client.pay_order.return_value = {"payment_status": "PAID"}
    client.print_order.return_value = {"status": "ERROR", "error_message": "offline"}
    window = PosMainWindow(client, SessionState("token", {"name": "Kassir"}), UiSettings(POS_PRINTER_ID=123), Mock())
    qt_app.processEvents()
    yield window
    window.close()


def test_no_order_until_save_delivery_required_and_saved_cart_locked(window):
    product = {"id": 510, "name": "Non", "base_price": 6000}
    window._add_product(product)
    window.cart_widget.items.setCurrentRow(0)
    window._change_cart_quantity(1)
    window.client.create_order.assert_not_called()
    window.delivery_button.click()
    window._save_order()
    window.client.create_order.assert_not_called()
    window.delivery_worker_combo.setCurrentIndex(1)
    window._save_order()
    payload = window.client.create_order.call_args.args[0]
    assert payload["delivery_worker_id"] == 99 and payload["order_type"] == "DELIVERY"
    assert payload["items"][0]["quantity"] == "2.000"
    assert window.current_order["payment_status"] == "PENDING"
    window._change_cart_quantity(1)
    window._remove_selected_cart_item()
    assert window.cart.items[0].quantity == 2
    assert not window.save_button.isEnabled()


def test_gui_print_failure_retains_paid_and_retry_never_repays(window):
    window._add_product({"id": 510, "name": "Non", "base_price": 12000})
    window._save_order()
    assert window.client.create_order.call_args.args[0]["order_type"] == "CHAYKHANA"
    window._checkout()
    assert window.current_order["payment_status"] == "PAID"
    assert window.checkout_button.text() == "QAYTA CHOP ETISH"
    assert not window.new_order_button.isHidden()
    window.client.print_order.return_value = {"status": "SUCCESS"}
    window._checkout()
    window.client.pay_order.assert_called_once_with(800)
    assert window.client.print_order.call_count == 2
    assert window.current_order is None and not window.cart.items


def test_payment_precedes_print_and_network_failure_preserves_paid():
    calls = []
    client = Mock()
    client.pay_order.side_effect = lambda order_id: calls.append("pay") or {"payment_status": "PAID"}
    def print_failure(*args):
        calls.append("print")
        raise ApiConnectionError("offline")
    client.print_order.side_effect = print_failure
    outcome = pay_and_print(client, 800, 123)
    assert calls == ["pay", "print"]
    assert outcome.payment["payment_status"] == "PAID" and not outcome.printed
    print_paid_order(client, 800, 123, outcome.payment)
    assert calls == ["pay", "print", "print"]


def test_logout_clears_session(window):
    window._logout()
    window.client.clear_session.assert_called_once()
    assert window.session.access_token == "" and window.session.user == {}
    window.on_logout.assert_called_once()


def test_lost_payment_response_reconciles_before_retry(window):
    window._add_product({"id": 510, "name": "Non", "base_price": 12000})
    window._save_order()
    window.client.pay_order.side_effect = ApiConnectionError("response lost")
    window._checkout()
    assert window.payment_uncertain
    window.client.get_order.return_value = {"id": 800, "order_number": "00800", "payment_status": "PAID", "total_amount": 12000}
    window._checkout()
    window.client.get_order.assert_called_once_with(800)
    window.client.pay_order.assert_called_once_with(800)
    assert window.current_order["payment_status"] == "PAID"
