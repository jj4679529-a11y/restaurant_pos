from copy import deepcopy
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.dialogs.saved_orders import OrderDetailDialog, SavedOrdersDialog
from app.ui.api_client import ApiConnectionError
from tests.test_ui_final_menu import qt_app, osh, window


def order(status='PENDING', id=900):
    return {'id': id, 'order_number': str(id), 'created_at': '2026-09-12T10:00:00+05:00',
            'order_type': 'CHAYKHANA', 'delivery_worker': None, 'payment_status': status,
            'total_amount': 32000, 'items': [
                {'product': {'id': 501, 'name': 'Osh'}, 'quantity': '1.000', 'unit_price': 17000,
                 'total_price': 17000, 'selected_price_option_id': 71,
                 'addons': [{'addon': {'name': "Go'sht"}, 'quantity': '1.000', 'unit_price': 15000, 'total_price': 15000}]}
            ]}


@pytest.mark.parametrize('configured', [True, False])
def test_osh_never_manual_even_if_backend_flag_is_wrong(qt_app, osh, monkeypatch, configured):
    osh['allows_manual_price'] = True
    if not configured:
        osh['price_options'] = []
    picker = Mock()
    monkeypatch.setattr(NumberDialog, 'money', picker)
    dialog = ProductDialog(osh)
    dialog._product_price()
    picker.assert_not_called()
    assert not any(b.text() == 'NARXNI TANLASH' for b in dialog.findChildren(QPushButton))
    if configured:
        assert len(dialog.options_group.buttons()) == 2
        dialog.options_group.buttons()[0].click()
        payload = dialog._item().to_payload()
        assert payload['selected_price_option_id'] == 71
        assert 'manual_price' not in payload
    else:
        assert not dialog.options_group.buttons()
        assert not dialog.confirm.isEnabled()
        assert 'narx' in dialog.total.text()
    dialog.close()


def test_gosht_inline_active_preset_and_empty_state(qt_app, osh, monkeypatch):
    gosht = osh['available_addons'][3]
    gosht['manual_price_presets'].append({'amount': 12345, 'is_active': False})
    picker = Mock(return_value=18200)
    monkeypatch.setattr(NumberDialog, 'money', picker)
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    buttons = dialog.findChildren(QPushButton)
    next(b for b in buttons if b.text() == '15 000 so‘m').click()
    assert not any(b.text() == '12 345 so‘m' for b in buttons)
    assert dialog._item().addons[0].manual_price == 15000
    picker.assert_not_called()
    next(b for b in buttons if b.text() == 'BOSHQA NARX').click()
    assert dialog._item().addons[0].manual_price == 18200
    dialog.close()
    gosht['manual_price_presets'] = []
    empty = ProductDialog(osh)
    assert any(l.text() == 'Tezkor narxlar sozlanmagan' for l in empty.findChildren(QLabel))
    assert any(b.text() == 'BOSHQA NARX' for b in empty.findChildren(QPushButton))
    empty.close()


def test_saved_list_newest_first_filter_and_page(qt_app):
    client = Mock()
    client.list_orders.return_value = [order(id=1), order(id=3), order(id=2)]
    dialog = SavedOrdersDialog(client, None, Mock())
    assert [dialog.rows.item(i).data(Qt.ItemDataRole.UserRole) for i in range(3)] == [3, 2, 1]
    dialog.filter('PAID')
    client.list_orders.assert_called_with('PAID', offset=0, limit=30)
    dialog.page(30)
    client.list_orders.assert_called_with('PAID', offset=30, limit=30)
    dialog.close()


@pytest.mark.parametrize('status', ['PENDING', 'PAID', 'CANCELLED'])
def test_saved_order_detail_readonly_and_status_actions(qt_app, status):
    client = Mock()
    client.get_order.return_value = order(status)
    dialog = OrderDetailDialog(client, 900, 123, Mock())
    assert dialog.details.isReadOnly()
    text = dialog.details.toPlainText()
    assert 'Osh' in text and "Go'sht" in text and '71' in text and '32 000' in text
    assert dialog.action.isHidden() == (status == 'CANCELLED')
    if status == 'CANCELLED':
        dialog.checkout()
        client.pay_order.assert_not_called()
        client.print_order.assert_not_called()
    dialog.close()


@pytest.mark.parametrize('printed', [True, False])
def test_saved_pending_pay_then_print_and_preserve_paid(qt_app, printed):
    client = Mock()
    stored = order()
    client.get_order.side_effect = lambda _: deepcopy(stored)
    events = []
    def pay(_):
        events.append('pay')
        stored['payment_status'] = 'PAID'
        return {'payment_status': 'PAID'}
    def print_order(*args):
        events.append('print')
        return {'status': 'SUCCESS' if printed else 'ERROR'}
    client.pay_order.side_effect = pay
    client.print_order.side_effect = print_order
    dialog = OrderDetailDialog(client, 900, 123, Mock())
    dialog.action.click()
    assert events == ['pay', 'print']
    assert dialog.order['payment_status'] == 'PAID'
    assert dialog.action.text() == 'QAYTA CHEK CHOP ETISH'
    dialog.action.click()
    assert events == ['pay', 'print', 'print']
    client.create_order.assert_not_called()
    dialog.close()


def test_reopened_paid_order_prints_only(qt_app):
    client = Mock()
    client.get_order.return_value = order('PAID')
    client.print_order.return_value = {'status': 'ERROR'}
    dialog = OrderDetailDialog(client, 900, 123, Mock())
    dialog.action.click()
    client.pay_order.assert_not_called()
    client.print_order.assert_called_once_with(900, 123)
    assert dialog.order['payment_status'] == 'PAID'
    dialog.close()


def test_saved_pay_timeout_rechecks_server_before_retry(qt_app):
    client = Mock()
    client.get_order.return_value = order()
    client.pay_order.side_effect = ApiConnectionError('lost response')
    client.print_order.return_value = {'status': 'ERROR'}
    dialog = OrderDetailDialog(client, 900, 123, Mock())
    dialog.action.click()
    client.get_order.return_value = order('PAID')
    dialog.action.click()
    client.pay_order.assert_called_once()
    client.print_order.assert_called_once()
    dialog.close()


def test_history_preserves_draft_and_new_order_keeps_saved_record(window, monkeypatch):
    window._add_product({'id': 510, 'name': 'Non', 'base_price': 12000})
    original = list(window.cart.items)
    window.client.list_orders.return_value = []
    monkeypatch.setattr(SavedOrdersDialog, 'exec', lambda self: self.reject())
    window.saved_orders_button.click()
    window.fresh_order_button.click()
    assert window.cart.items == original
    window.client.create_order.assert_not_called()
    window._save_order()
    saved_id = window.current_order['id']
    window.fresh_order_button.click()
    assert window.current_order is None and not window.cart.items
    window.client.create_order.assert_called_once()
    assert saved_id == 800
    window.client.pay_order.assert_not_called()
