"""Focused business-rule UI tests; no restaurant orders are created."""
import os
from decimal import Decimal
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QScroller, QScrollArea, QPushButton, QLabel, QMessageBox

from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.main_window import PosMainWindow
from app.ui.widgets.product_card import ProductCard
from app.ui.config import UiSettings
from app.ui.state import CartValidationError, SessionState
from tests.test_ui_final_menu import qt_app, osh
from tests.ui_helpers import wait_for_catalog


# ---- Osh grouping ----

def test_osh_single_product_card_for_two_portions(qt_app, osh):
    product = {"id": 501, "name": "Osh", "base_price": 0, "allows_manual_price": False,
               "price_options": [
                   {"id": 1, "name": "0.5 porsiya", "quantity": "0.500", "price": 17000, "is_active": True},
                   {"id": 2, "name": "1 porsiya", "quantity": "1.000", "price": 31000, "is_active": True},
               ],
               "available_addons": []}
    card = ProductCard(product)
    assert "Osh" in card.text()
    assert "17 000" in card.text()
    card.close()


def test_osh_opens_portion_dialog_from_card(qt_app, osh):
    dialog = ProductDialog(osh)
    assert len(dialog.options_group.buttons()) == 2
    dialog.options_group.buttons()[0].click()
    assert dialog._item().total_price == 17000
    dialog.options_group.buttons()[1].click()
    assert dialog._item().total_price == 31000
    dialog.close()


def test_osh_only_o_sh_gets_portion_grouping(qt_app):
    non_osh = {"id": 601, "name": "Non", "base_price": 6000, "allows_manual_price": False,
               "price_options": [{"id": 1, "name": "Butun", "quantity": "1", "price": 6000, "is_active": True}],
               "available_addons": []}
    dialog = ProductDialog(non_osh)
    assert dialog.is_osh is False
    assert len(dialog.options_group.buttons()) == 1
    dialog.close()


# ---- Osh addons: quantity only ----

def test_osh_addon_tuxum_quantity_only(qt_app, osh):
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    tuxum = osh["available_addons"][0]
    dialog._addon_count(tuxum, 2)
    addon = dialog._item().addons[0]
    assert addon.quantity == Decimal(2)
    assert addon.unit_price == tuxum["base_price"]
    dialog.close()


def test_osh_addon_bedana_and_qazi_quantity_only(qt_app, osh):
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    for addon in osh["available_addons"][1:3]:
        dialog._addon_count(addon, 1)
    addons = dialog._item().addons
    assert all(a.quantity == Decimal(1) for a in addons)
    dialog.close()


# ---- Jizz: max 4 presets, manual amount, no fixed price ----

def test_jizz_max_four_presets_visible(qt_app):
    product = {"id": 700, "name": "Jizz", "unit_type": "AMOUNT", "base_price": 0,
               "allows_manual_price": True,
               "manual_price_presets": [{"amount": 10000 + i * 5000, "is_active": True} for i in range(6)]}
    dialog = ProductDialog(product)
    money_buttons = [b for b in dialog.findChildren(QPushButton) if "so‘m" in b.text()]
    assert len(money_buttons) == 4
    dialog.close()


def test_jizz_manual_amount_works(qt_app, monkeypatch):
    product = {"id": 701, "name": "Jizz", "unit_type": "AMOUNT", "base_price": 0,
               "allows_manual_price": True,
               "manual_price_presets": [{"amount": 50000, "is_active": True}]}
    dialog = ProductDialog(product)
    monkeypatch.setattr(NumberDialog, "money", lambda *a, **kw: 50000)
    dialog._product_price()
    item = dialog._item()
    assert item.manual_price == 50000
    dialog.close()


def test_jizz_no_fixed_price_flow(qt_app):
    product = {"id": 702, "name": "Jizz", "unit_type": "AMOUNT", "base_price": 0,
               "allows_manual_price": True,
               "manual_price_presets": [{"amount": 50000, "is_active": True}]}
    dialog = ProductDialog(product)
    assert dialog.is_liter is False
    assert not dialog.is_osh
    assert len(dialog.options_group.buttons()) == 0
    dialog.close()


# ---- Cold drinks: no liter dialog, piece flow ----

def test_kompot_ayron_no_liter_entry_dialog(qt_app):
    kompot = {"id": 801, "name": "Kompot", "base_price": 6000, "unit_type": "PIECE",
              "allows_manual_price": False, "price_options": [], "available_addons": []}
    dialog = ProductDialog(kompot)
    assert dialog.is_liter is False
    volume_buttons = [b for b in dialog.findChildren(QPushButton) if 'L' in b.text() and 'litr' in b.text().casefold()]
    assert len(volume_buttons) == 0
    dialog.close()


def test_kompot_piece_quantity_only(qt_app):
    kompot = {"id": 801, "name": "Kompot", "base_price": 6000, "unit_type": "PIECE",
              "allows_manual_price": False, "price_options": [], "available_addons": []}
    dialog = ProductDialog(kompot)
    assert not dialog.is_liter
    dialog._count(1)
    item = dialog._item()
    assert item.quantity == Decimal(2)
    dialog.close()


# ---- Cold drink size metadata ----

def test_cold_drink_size_metadata_displayed(qt_app):
    drink = {"id": 802, "name": "Ayron", "base_price": 6000, "unit_type": "LITER",
             "volume_liters": 1.5, "allows_manual_price": False,
             "price_options": [], "available_addons": []}
    dialog = ProductDialog(drink)
    card = ProductCard(drink)
    assert "1.5" in card.text() or "1,5" in card.text()
    dialog.close()


# ---- Category ordering: Barchasi first ----

def test_category_barchasi_first_in_main_window(qt_app, monkeypatch):
    client = Mock()
    client.load_image.return_value = None
    categories = [{"id": 2, "name": "Milliy taomlar"}, {"id": 1, "name": "Barchasi"}]
    products = [{"id": n, "category_id": 1, "name": f"Mahsulot {n}", "base_price": 5000} for n in range(3)]
    client.load_catalog.return_value = (categories, products, [])
    window = PosMainWindow(client, SessionState("token", {"name": "Kassir"}),
                           UiSettings(), lambda: None)
    wait_for_catalog(window, qt_app)
    cat_buttons = window.category_content.findChildren(QPushButton)
    assert len(cat_buttons) >= 2
    assert "BARCHASI" in cat_buttons[0].text().upper()
    window.close()


# ---- Touch scroll verification ----

def test_main_window_category_scroll_has_qscroller(qt_app, monkeypatch):
    client = Mock()
    client.load_image.return_value = None
    categories = [{"id": 1, "name": "Test"}]
    products = [{"id": n, "category_id": 1, "name": f"Item {n}", "base_price": 5000} for n in range(3)]
    client.load_catalog.return_value = (categories, products, [])
    window = PosMainWindow(client, SessionState("token", {"name": "Kassir"}),
                           UiSettings(), lambda: None)
    wait_for_catalog(window, qt_app)
    assert window.category_scroll is not None
    assert QScroller.scroller(window.category_scroll.viewport()) is not None
    window.close()


def test_main_window_product_scroll_has_qscroller(qt_app, monkeypatch):
    client = Mock()
    client.load_image.return_value = None
    categories = [{"id": 1, "name": "Test"}]
    products = [{"id": n, "category_id": 1, "name": f"Item {n}", "base_price": 5000} for n in range(3)]
    client.load_catalog.return_value = (categories, products, [])
    window = PosMainWindow(client, SessionState("token", {"name": "Kassir"}),
                           UiSettings(), lambda: None)
    wait_for_catalog(window, qt_app)
    assert window.product_scroll is not None
    assert QScroller.scroller(window.product_scroll.viewport()) is not None
    window.close()


# ---- Admin QScroller on long menus ----

def test_admin_quick_prices_has_qscroller(qt_app):
    from app.ui.admin.menu_settings import QuickPricesDialog
    from app.ui.api_client import PosApiClient
    client = PosApiClient('http://testserver', transport=lambda *a, **kw: None)
    addon = {"id": 1, "name": "Test", "price": 1000}
    dialog = QuickPricesDialog(client, 'addons', addon, lambda e: None)
    scroll = dialog.findChild(QScrollArea)
    assert scroll is not None
    assert QScroller.scroller(scroll.viewport()) is not None
    dialog.close()


# ---- Cashier cannot edit configured price via dialog ----

def test_cashier_cannot_edit_configured_price_dialog(qt_app, osh):
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    item = dialog._item()
    price_before = item.unit_price
    dialog.close()
    assert price_before == 17000


# ---- Image placeholder ----

def test_product_image_placeholder_when_missing(qt_app, osh):
    card = ProductCard(osh)
    assert not card.icon().isNull()
    card.close()
