"""Restaurant-facing editors over the existing catalog API (no pricing logic)."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QSpinBox, QFormLayout, QDialog, QScrollArea, QMessageBox)

from app.ui.admin.api import menu_name
from app.ui.admin.forms import Editor
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.state import format_money


class QuickPricesDialog(QDialog):
    def __init__(self, client, resource, target, on_error, parent=None):
        super().__init__(parent)
        self.client, self.target, self.on_error = client, target, on_error
        self.field = 'product_id' if resource == 'products' else 'addon_id'
        self.setWindowTitle(target['name'] + ' — Tezkor narxlar')
        self.resize(600, 560)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(target['name'] + '\nNarxni kassir kiritadi'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.rows = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        add = QPushButton('+ TEZKOR NARX QO‘SHISH')
        add.setProperty('primary', True)
        add.clicked.connect(lambda: self.edit())
        layout.addWidget(add)
        close = QPushButton('YOPISH')
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.load()

    def load(self):
        try:
            records = [r for r in self.client.list_records('presets') if r.get(self.field) == self.target['id']]
        except Exception as error:
            self.on_error(error)
            return
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for record in records:
            row = QWidget()
            line = QHBoxLayout(row)
            line.addWidget(QLabel(format_money(record['amount']) + (' · Nofaol' if not record['is_active'] else '')), 1)
            edit = QPushButton('Tahrirlash')
            edit.clicked.connect(lambda _=False, r=record: self.edit(r))
            line.addWidget(edit)
            toggle = QPushButton('Nofaol qilish' if record['is_active'] else 'Faollashtirish')
            toggle.clicked.connect(lambda _=False, r=record: self.toggle(r))
            line.addWidget(toggle)
            self.rows.addWidget(row)
        self.rows.addStretch()

    def edit(self, original=None):
        amount = NumberDialog.money(self, 'Tezkor narx', initial=(original or {}).get('amount', 0))
        if amount is None:
            return
        try:
            data = {'amount': amount}
            if original is None:
                data[self.field] = self.target['id']
            self.client.save_record('presets', data, original)
            self.load()
        except Exception as error:
            self.on_error(error)

    def toggle(self, record):
        if QMessageBox.question(self, 'Tasdiqlash', 'Tezkor narx faolligini o‘zgartirasizmi?') != QMessageBox.StandardButton.Yes:
            return
        try:
            self.client.save_record('presets', {'is_active': not record['is_active']}, record)
            self.load()
        except Exception as error:
            self.on_error(error)


class OshPage(QWidget):
    def __init__(self, client, on_error, parent=None):
        super().__init__(parent)
        self.client, self.on_error = client, on_error
        self.product = None
        self.initial = (0, 0)
        layout = QVBoxLayout(self)
        title = QLabel('Osh sozlamalari')
        title.setObjectName('dialogTitle')
        layout.addWidget(title)
        layout.addWidget(QLabel('Porsiya narxlari'))
        form = QFormLayout()
        self.prices = {}
        for key, title in [('half_price', '0.5 porsiya'), ('full_price', '1 porsiya')]:
            row = QHBoxLayout()
            spin = QSpinBox()
            spin.setRange(0, 2_147_483_647)
            spin.setSuffix(' so‘m')
            self.prices[key] = spin
            row.addWidget(spin)
            keypad = QPushButton('Narx kiritish')
            keypad.clicked.connect(lambda _=False, field=spin: self.number(field))
            row.addWidget(keypad)
            form.addRow(title, row)
        layout.addLayout(form)
        self.save_button = QPushButton('PORSIYA NARXLARINI SAQLASH')
        self.save_button.setProperty('primary', True)
        self.save_button.clicked.connect(self.save)
        layout.addWidget(self.save_button)
        self.notice = QLabel('Qo‘shimchalar va tezkor narxlar alohida saqlanadi.')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.addons = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def number(self, field):
        amount = NumberDialog.money(self, 'Porsiya narxi', initial=field.value())
        if amount is not None:
            field.setValue(amount)

    def load(self):
        try:
            product = next((p for p in self.client.list_records('products') if menu_name(p['name']) == 'osh' and p['is_active']), None)
            self.product = product
            self.save_button.setEnabled(product is not None)
            if product is None:
                self.notice.setText('Faol Osh topilmadi. Menyuni tekshiring.')
                return
            for key, name in [('half_price', '0.5 porsiya'), ('full_price', '1 porsiya')]:
                self.prices[key].setValue(next((p['price'] for p in product['price_options'] if p['name'] == name and p['is_active']), 0))
            self.initial = tuple(p.value() for p in self.prices.values())
            while self.addons.count():
                item = self.addons.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for addon in product.get('available_addons', []):
                row = QWidget()
                line = QHBoxLayout(row)
                line.addWidget(QLabel(addon['name']), 1)
                manual = addon['allows_manual_price']
                line.addWidget(QLabel('Narxni kassir kiritadi' if manual else format_money(addon['base_price']) + ' / dona'))
                edit = QPushButton('Tezkor narxlar' if manual else 'Narxni o‘zgartirish')
                edit.clicked.connect(lambda _=False, a=addon: self.edit_addon(a))
                line.addWidget(edit)
                self.addons.addWidget(row)
            self.addons.addStretch()
        except Exception as error:
            self.on_error(error)

    def can_leave(self):
        if tuple(p.value() for p in self.prices.values()) == self.initial:
            return True
        return QMessageBox.question(self, 'Saqlanmagan narxlar', 'Narxlarni saqlamasdan chiqasizmi?',
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def save(self):
        if not self.product:
            return
        try:
            data = {key: field.value() for key, field in self.prices.items()}
            if not all(data.values()):
                raise ValueError('Ikkala porsiya narxini kiriting')
            self.client.save_osh_prices(self.product['id'], **data)
            self.initial = tuple(p.value() for p in self.prices.values())
            self.notice.setText('✓ Saqlandi. Kassir menyuni yangilashi mumkin.')
        except Exception as error:
            self.on_error(error)

    def edit_addon(self, addon):
        draft = {key: field.value() for key, field in self.prices.items()}
        initial = self.initial
        if addon['allows_manual_price']:
            QuickPricesDialog(self.client, 'addons', addon, self.on_error, self).exec()
        else:
            def save(data):
                self.client.save_record('addons', {'name': addon['name'], **data}, addon)
            Editor(addon['name'], [('base_price', 'Dona narxi', 'money')], addon, save, self.on_error, self).exec()
        self.load()
        # Refresh addon summaries without overwriting the owner's portion draft.
        for key, value in draft.items():
            self.prices[key].setValue(value)
        self.initial = initial
