from decimal import Decimal
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QPushButton

from app.seed.runner import seed_all
from app.ui.admin.menu_settings import QuickPricesDialog
from app.ui.admin.forms import Editor, RecordEditor
from app.ui.admin.menu_wizard import StrictEditDialog
from app.ui.admin.admin_window import AdminWindow
from app.ui.config import UiSettings
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.main_window import PosMainWindow
from app.ui.state import SessionState, CartItem
from app.ui.styles import APP_STYLESHEET
from tests.test_admin_ui import admin_http, dispose_test_windows
from tests.test_ui_final_menu import qt_app
from tests.test_seed import _settings


@pytest.fixture
def theme(qt_app):
    previous = qt_app.styleSheet()
    qt_app.setStyleSheet(APP_STYLESHEET)
    yield
    qt_app.setStyleSheet(previous)


@pytest.mark.parametrize('size', [(1280, 720), (1366, 768), (1600, 900), (1920, 1080)])
def test_cashier_geometry_actions_and_cart_lines(qt_app, theme, size):
    client = Mock()
    client.load_image.return_value = None
    products = [{'id': n, 'category_id': 1, 'name': f'Mahsulot {n}', 'base_price': 5000} for n in range(12)]
    client.load_catalog.return_value = ([{'id': 1, 'name': 'Milliy taomlar'}], products, [])
    window = PosMainWindow(client, SessionState('fixture', {'name': 'Kassir'}), UiSettings(), lambda: None)
    window.resize(*size)
    window.show()
    for _ in range(3):
        qt_app.processEvents()
    assert window.size().width() <= size[0]
    assert window.save_button.isVisible() and not window.checkout_button.isVisible()
    assert window.cart_widget.empty.isVisible()
    assert window.save_button.mapTo(window, window.save_button.rect().bottomRight()).y() < window.height()
    window.delivery_button.click()
    assert window.delivery_container.isVisible() and window.delivery_button.isChecked()
    window.chaykhana_button.click()
    assert not window.delivery_container.isVisible()
    window.cart.add(CartItem(1, 'Non', Decimal(1), 5000))
    window.cart_widget.render(window.cart)
    row = window.cart_widget.items.itemWidget(window.cart_widget.items.item(0))
    next(b for b in row.findChildren(QPushButton) if b.text() == '+').click()
    assert window.cart.items[0].quantity == 2
    for state in ('PENDING', 'PAID', 'CANCELLED'):
        window.current_order = {'payment_status': state}
        window._sync_actions()
        assert not window.save_button.isVisible()
        assert window.checkout_button.isVisible() == (state != 'CANCELLED')
        assert window.new_order_button.isVisible() == (state == 'PAID')
    window.current_order = None
    window._sync_actions()
    qt_app.processEvents()
    if size == (1366, 768):
        window.grab().save('/private/tmp/pos-ux-cashier.png')
    window.close()


def test_selectable_osh_and_addon_quick_prices_reach_cashier(
    db,
    qt_app,
    theme,
    admin_http,
    monkeypatch,
):
    client, auth, _ = admin_http
    seed_all(db, _settings())

    product = next(
        p for p in client.list_records("products")
        if p["name"] == "Osh"
    )

    # Yangi Osh editorida porsiyalar majburiy emas:
    # admin qaysilarini sotishni o'zi tanlaydi.
    category = next(
        c for c in client.list_records("categories")
        if c["id"] == product["category_id"]
    )

    dialog = StrictEditDialog(
        client,
        "Osh",
        category,
        product,
        lambda e: pytest.fail(str(e)),
    )

    dialog.osh_option_buttons["0.5 porsiya"].setChecked(True)
    dialog.osh_half_price.setValue(25000)

    dialog.osh_option_buttons["0.7 porsiya"].setChecked(True)
    dialog.osh_seven_price.setValue(35000)

    dialog.osh_option_buttons["1 porsiya"].setChecked(False)

    dialog._save_osh_options(product["id"])

    product = next(
        p for p in client.load_catalog()[1]
        if p["id"] == product["id"]
    )

    active_options = [
        option
        for option in product["price_options"]
        if option.get("is_active")
    ]

    assert {
        (o["name"], o["price"])
        for o in active_options
    } == {
        ("0.5 porsiya", 25000),
        ("0.7 porsiya", 35000),
    }

    cashier_dialog = ProductDialog(product)

    texts = [
        button.text()
        for button in cashier_dialog.options_group.buttons()
    ]

    assert any(
        "0.5 porsiya" in text and "25 000" in text
        for text in texts
    )

    assert any(
        "0.7 porsiya" in text and "35 000" in text
        for text in texts
    )

    assert not any(
        "1 porsiya" in text
        for text in texts
    )

    egg = next(
        a for a in product["available_addons"]
        if a["name"] == "Tuxum 1"
    )

    def save_price(editor):
        editor.widgets["base_price"].setValue(8000)
        editor.save()
        return editor.result()

    monkeypatch.setattr(Editor, "exec", save_price)

    # Qo'shimcha narxi mavjud umumiy editor orqali ishlaydi.
    client.save_record(
        "addons",
        {
            "name": egg["name"],
            "base_price": 8000,
        },
        egg,
    )

    meat = next(
        a for a in product["available_addons"]
        if a["allows_manual_price"]
    )

    quick = QuickPricesDialog(
        client,
        "addons",
        meat,
        lambda e: pytest.fail(str(e)),
    )

    monkeypatch.setattr(
        NumberDialog,
        "money",
        lambda *a, **kw: 27000,
    )

    quick.edit()

    product = next(
        p for p in client.load_catalog()[1]
        if p["id"] == product["id"]
    )

    assert next(
        a for a in product["available_addons"]
        if a["id"] == egg["id"]
    )["base_price"] == 8000

    assert any(
        preset["amount"] == 27000
        for addon in product["available_addons"]
        if addon["id"] == meat["id"]
        for preset in addon["manual_price_presets"]
    )

    cashier = ProductDialog(product)

    assert any(
        "27 000" in button.text()
        for button in cashier.findChildren(QPushButton)
    )

    window = AdminWindow(
        client,
        SessionState(
            auth["access_token"],
            auth["user"],
        ),
        lambda: None,
    )

    window.show()
    qt_app.processEvents()

    # Eski yashirin 'osh' sahifasi endi yo'q.
    assert "osh" not in window.pages

    window.grab().save(
        "/private/tmp/pos-ux-admin.png"
    )
    window.close()


def test_product_editor_hides_technical_image_and_manual_fields(db, qt_app, admin_http):
    client, _, _ = admin_http
    seed_all(db, _settings())
    product = next(p for p in client.list_records('products') if p['name'] == 'Jizz')
    editor = RecordEditor('products', client, product, lambda e: pytest.fail(str(e)))
    assert editor.widgets['image_path'].isHidden()
    assert editor.widgets['base_price'].isHidden()
    assert editor.widgets['unit_type'].isHidden()
    assert editor.widgets['allows_manual_price'].isChecked()
    assert editor.preview is not None
