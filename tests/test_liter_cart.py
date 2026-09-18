from decimal import Decimal
from uuid import uuid4

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QLabel, QPushButton, QFormLayout

from app.models import Category, Product, UnitType
from app.ui.admin.forms import RecordEditor
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.dialogs.volume_dialog import VolumeDialog, parse_volume
from app.ui.state import Cart, CartItem, CartAddOn, CartValidationError, format_quantity
from app.ui.widgets.cart_widget import CartWidget
from app.ui.widgets.product_card import ProductCard
from tests.test_admin_ui import admin_http, dispose_test_windows
from tests.test_ui_final_menu import qt_app
from tests.test_ux_refinement import theme


def drink(price=12000):
    return {'id': 901, 'name': 'Legacy litrli mahsulot', 'category_id': 1, 'unit_type': 'LITER',
            'base_price': price, 'allows_manual_price': False, 'price_options': [], 'available_addons': []}


@pytest.mark.parametrize('volume,total', [('0.5', 6000), ('1', 12000), ('1.5', 18000), ('2', 24000)])
def test_liter_quick_volume_and_payload(qt_app, volume, total):
    dialog = ProductDialog(drink())
    next(b for b in dialog.volume_group.buttons() if b.text() == volume + ' L').click()
    item = dialog._item()
    assert item.quantity == Decimal(volume)
    assert item.unit_price == 12000 and item.total_price == total
    assert item.unit_type == 'LITER'
    payload = item.to_payload()
    assert Decimal(payload['quantity']) == Decimal(volume)
    assert 'unit_type' not in payload and 'manual_price' not in payload


@pytest.mark.parametrize('text', ['0.25', '0.75', '1.5', '1,5', '2.5'])
def test_custom_decimal_volume(qt_app, text):
    keypad = VolumeDialog()
    keypad.input.setText(text)
    assert keypad.confirm.isEnabled()
    assert parse_volume(text) == Decimal(text.replace(',', '.'))


@pytest.mark.parametrize('text', ['0', '-1', 'invalid', '', 'NaN', '1.0001', '1..5'])
def test_invalid_volume_cannot_be_confirmed(qt_app, text):
    keypad = VolumeDialog()
    keypad.input.setText(text)
    assert not keypad.confirm.isEnabled()
    keypad.accept()
    assert keypad.result() == 0
    with pytest.raises(ValueError):
        parse_volume(text)


def test_custom_volume_edit_and_fractional_money_rejection(qt_app, monkeypatch):
    existing = CartItem.from_catalog(drink(), Decimal('0.750'))
    dialog = ProductDialog(drink(), existing)
    monkeypatch.setattr(VolumeDialog, 'choose', lambda *a: Decimal('2.5'))
    dialog._custom_volume()
    assert dialog._item().total_price == 30000
    invalid = ProductDialog(drink(1))
    invalid._volume(Decimal('0.5'))
    assert not invalid.confirm.isEnabled()
    with pytest.raises(CartValidationError):
        invalid._item()


@pytest.mark.parametrize('quantity,expected', [('1.000', '1'), ('0.500', '0.5'), ('1.500', '1.5')])
def test_quantity_format(quantity, expected):
    assert format_quantity(Decimal(quantity)) == expected


def test_light_receipt_and_liter_line(qt_app, theme):
    old = qt_app.palette()
    dark = QPalette(old)
    dark.setColor(QPalette.ColorRole.Window, QColor('black'))
    dark.setColor(QPalette.ColorRole.Base, QColor('black'))
    qt_app.setPalette(dark)
    try:
        cart = Cart()
        cart.add(CartItem(1, 'Osh', Decimal('1.000'), 25000, option_name='0.5 porsiya', addons=(
            CartAddOn(2, 'Tuxum 1', Decimal('1.000'), 5000),)))
        cart.add(CartItem.from_catalog(drink(), Decimal('1.500')))
        widget = CartWidget()
        widget.resize(420, 720)
        widget.render(cart)
        widget.show()
        qt_app.processEvents()
        assert widget.items.viewport().palette().color(QPalette.ColorRole.Base).lightness() > 200
        first = widget.items.itemWidget(widget.items.item(0))
        texts = [l.text() for l in first.findChildren(QLabel)]
        assert '1' in texts and not any('1.000' in t or '=' in t for t in texts)
        assert any('0.5 porsiya' in t for t in texts)
        second = widget.items.itemWidget(widget.items.item(1))
        texts = [l.text() for l in second.findChildren(QLabel)]
        assert 'Legacy litrli mahsulot — 1.5 L' in texts and '18 000 so‘m' in texts
        assert '12 000 so‘m / litr' in texts
        assert not any(b.text() in ('−', '+') for b in second.findChildren(QPushButton))
        widget.items.setCurrentRow(1)
        assert second.property('selected') is True
        widget.grab().save('/private/tmp/pos-liter-receipt.png')
        assert '12 000 so‘m / litr' in ProductCard(drink()).text()
        widget.close()
    finally:
        qt_app.setPalette(old)


def test_admin_kompot_piece_price_to_cashier_and_backend_order(db, qt_app, admin_http):
    client, _, _ = admin_http

    category = Category(name='Kompot va Ayron ' + uuid4().hex)

    product = Product(
        category=category,
        name='Kompot ' + uuid4().hex,
        unit_type=UnitType.PIECE,
        base_price=12000,
        allows_manual_price=False,
    )

    db.add(product)
    db.flush()

    product_id = product.id

    original = client.get(f'/api/products/{product_id}')

    editor = RecordEditor(
        'products',
        client,
        original,
        lambda e: pytest.fail(str(e)),
    )

    label = editor.form.itemAt(
        editor.field_rows['base_price'],
        QFormLayout.ItemRole.LabelRole,
    ).widget()

    assert label.text() == 'Dona narxi'

    editor.widgets['base_price'].setValue(14000)
    editor.save()

    refreshed = next(
        p for p in client.load_catalog()[1]
        if p['id'] == product_id
    )

    assert refreshed['base_price'] == 14000
    assert refreshed['unit_type'] == 'PIECE'

    picker = ProductDialog(refreshed)
    item = picker._item()

    assert item.total_price == 14000
    assert item.quantity == Decimal('1')

    order = client.create_order({
        'order_type': 'CHAYKHANA',
        'items': [item.to_payload()],
    })

    assert order['total_amount'] == 14000
    assert order['payment_status'] == 'PENDING'
    assert Decimal(order['items'][0]['quantity']) == Decimal('1')
    assert order['items'][0]['unit_price'] == 14000