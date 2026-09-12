"""Read-only history; payment/print actions reuse the existing HTTP flow."""
from datetime import datetime
from zoneinfo import ZoneInfo
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QButtonGroup

from app.ui.api_client import ApiAuthenticationError
from app.ui.checkout import pay_and_print, print_paid_order
from app.ui.state import format_money


def report_error(dialog, error):
    if isinstance(error, ApiAuthenticationError):
        dialog.reject()
        parent = dialog.parentWidget()
        if isinstance(parent, QDialog):
            parent.reject()
    dialog.on_error(error)


def order_text(order):
    worker = (order.get('delivery_worker') or {}).get('name', '')
    created = order.get('created_at', '')
    if created:
        created = datetime.fromisoformat(created).astimezone(ZoneInfo('Asia/Tashkent')).strftime('%d.%m.%Y %H:%M')
    kind = 'CHOYXONADA' if order['order_type'] == 'CHAYKHANA' else 'YETKAZIB BERISH'
    return f"#{order['order_number']} · {created}\n{kind} {worker} · {format_money(order['total_amount'])} · {order['payment_status']}"


class OrderDetailDialog(QDialog):
    def __init__(self, client, order_id, printer_id, on_error, parent=None):
        super().__init__(parent)
        self.client, self.order_id, self.printer_id, self.on_error = client, order_id, printer_id, on_error
        self.order = None
        self.setWindowTitle('Buyurtma tafsilotlari')
        self.resize(760, 650)
        layout = QVBoxLayout(self)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.action = QPushButton()
        self.action.clicked.connect(self.checkout)
        layout.addWidget(self.action)
        back = QPushButton('ORQAGA / YANGI BUYURTMAGA QAYTISH')
        back.clicked.connect(self.accept)
        layout.addWidget(back)
        self.refresh()

    def refresh(self):
        try:
            self.order = self.client.get_order(self.order_id)
        except Exception as error:
            self.action.setEnabled(False)
            report_error(self, error)
            return False
        self.render()
        return True

    def render(self):
        lines = [order_text(self.order), '']
        for item in self.order.get('items', []):
            variant = item.get('selected_price_option_id')
            lines.append(f"{item['product']['name']} × {item['quantity']} · {format_money(item['unit_price'])} = {format_money(item['total_price'])}")
            if variant is not None:
                lines.append(f'  Tanlangan PriceOption ID: {variant}')
            for addon in item.get('addons', []):
                lines.append(f"  + {addon['addon']['name']} × {addon['quantity']} · {format_money(addon['unit_price'])} = {format_money(addon['total_price'])}")
        self.details.setPlainText('\n'.join(lines))
        state = self.order['payment_status']
        self.action.setVisible(state in {'PENDING', 'PAID'})
        self.action.setEnabled(state in {'PENDING', 'PAID'})
        self.action.setText('QAYTA CHEK CHOP ETISH' if state == 'PAID' else 'CHEK CHOP ETISH / TO‘LASH')

    def checkout(self):
        self.action.setEnabled(False)
        # Always reconcile stale/timeout state before considering payment.
        if not self.refresh():
            return
        self.action.setEnabled(False)
        state = self.order['payment_status']
        if state not in {'PENDING', 'PAID'}:
            return
        try:
            if state == 'PAID':
                outcome = print_paid_order(self.client, self.order_id, self.printer_id, self.order)
            else:
                outcome = pay_and_print(self.client, self.order_id, self.printer_id)
        except Exception as error:
            self.status.setText('Natija tasdiqlanmadi. Keyingi urinishda server holati tekshiriladi.')
            self.action.setEnabled(True)
            report_error(self, error)
            return
        self.order['payment_status'] = outcome.payment['payment_status']
        self.render()
        message = 'To‘lov saqlandi. Chek chiqarildi.' if outcome.printed else 'To‘lov saqlandi. Chek chiqarilmadi.'
        if not outcome.printer_configured:
            message += ' Printer sozlanmagan.'
        self.status.setText(message)


class SavedOrdersDialog(QDialog):
    def __init__(self, client, printer_id, on_error, parent=None):
        super().__init__(parent)
        self.client, self.printer_id, self.on_error = client, printer_id, on_error
        self.filter_status = None
        self.offset = 0
        self.setWindowTitle('SAQLANGAN BUYURTMALAR')
        self.resize(950, 650)
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        group = QButtonGroup(self)
        for status in (None, 'PENDING', 'PAID', 'CANCELLED'):
            button = QPushButton(status or 'BARCHASI')
            button.setCheckable(True)
            button.setChecked(status is None)
            group.addButton(button)
            button.clicked.connect(lambda _=False, value=status: self.filter(value))
            filters.addWidget(button)
        layout.addLayout(filters)
        self.rows = QListWidget()
        self.rows.setWordWrap(True)
        self.rows.itemClicked.connect(self.open_order)
        layout.addWidget(self.rows)
        self.message = QLabel()
        layout.addWidget(self.message)
        actions = QHBoxLayout()
        self.previous = QPushButton('OLDINGI')
        self.previous.clicked.connect(lambda: self.page(-30))
        self.next = QPushButton('KEYINGI')
        self.next.clicked.connect(lambda: self.page(30))
        back = QPushButton('YANGI BUYURTMAGA QAYTISH')
        back.clicked.connect(self.accept)
        for button in (self.previous, self.next, back):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.reload()

    def filter(self, status):
        self.filter_status, self.offset = status, 0
        self.reload()

    def page(self, delta):
        self.offset = max(0, self.offset + delta)
        self.reload()

    def reload(self):
        self.rows.clear()
        try:
            orders = self.client.list_orders(self.filter_status, offset=self.offset, limit=30)
        except Exception as error:
            self.message.setText('Buyurtmalar yuklanmadi')
            report_error(self, error)
            return
        for order in sorted(orders, key=lambda o: o['id'], reverse=True):
            row = QListWidgetItem(order_text(order))
            row.setData(Qt.ItemDataRole.UserRole, order['id'])
            row.setSizeHint(QSize(0, 100))
            self.rows.addItem(row)
        self.message.setText('Buyurtmalar yo‘q' if not orders else 'Tafsilotlar uchun buyurtmani bosing')
        self.previous.setEnabled(self.offset > 0)
        self.next.setEnabled(len(orders) == 30)

    def open_order(self, item):
        dialog = OrderDetailDialog(self.client, item.data(Qt.ItemDataRole.UserRole), self.printer_id, self.on_error, self)
        dialog.exec()
        self.reload()
