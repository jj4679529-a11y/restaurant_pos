from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QComboBox, QInputDialog, QMessageBox

from app.ui.admin.forms import Editor, RecordEditor
from app.ui.admin.api import menu_name
from app.ui.state import format_money

TITLES = {'categories': 'Kategoriyalar', 'products': 'Mahsulotlar', 'addons': 'Qo‘shimchalar',
          'presets': 'Narx presetlari', 'workers': 'Yetkazib beruvchilar', 'users': 'Kassirlar / foydalanuvchilar',
          'printers': 'Printerlar', 'settings': 'Sozlamalar'}


class ResourcePage(QWidget):
    def __init__(self, resource, client, on_error, parent=None):
        super().__init__(parent)
        self.resource, self.client, self.on_error = resource, client, on_error
        self.records = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(TITLES[resource]))
        self.category = QComboBox()
        self.category.addItem('Barcha kategoriyalar', None)
        self.category.currentIndexChanged.connect(self.render)
        self.category.setVisible(resource == 'products')
        layout.addWidget(self.category)
        self.rows = QListWidget()
        self.rows.setWordWrap(True)
        self.rows.itemDoubleClicked.connect(lambda _: self.edit())
        layout.addWidget(self.rows)
        actions = QHBoxLayout()
        self.add_button = QPushButton('+ QO‘SHISH')
        self.add_button.setVisible(resource != 'settings')
        self.add_button.clicked.connect(lambda: self.edit(new=True))
        self.edit_button = QPushButton('TAHRIRLASH')
        self.edit_button.clicked.connect(lambda: self.edit())
        refresh = QPushButton('YANGILASH')
        refresh.clicked.connect(self.load)
        for button in (self.add_button, self.edit_button, refresh):
            actions.addWidget(button)
        layout.addLayout(actions)
        if resource == 'products':
            extra = QHBoxLayout()
            osh = QPushButton('OSH: 0.5 / 1 NARXLARI')
            osh.clicked.connect(self.osh_prices)
            links = QPushButton('QO‘SHIMCHA BOG‘LASH / AJRATISH')
            links.clicked.connect(self.links)
            extra.addWidget(osh)
            extra.addWidget(links)
            layout.addLayout(extra)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)

    def selected(self):
        item = self.rows.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def load(self):
        try:
            records = self.client.list_records(self.resource)
            if self.resource == 'products':
                selected = self.category.currentData()
                self.category.blockSignals(True)
                self.category.clear()
                self.category.addItem('Barcha kategoriyalar', None)
                for row in self.client.list_records('categories'):
                    self.category.addItem(row['name'], row['id'])
                self.category.setCurrentIndex(max(0, self.category.findData(selected)))
                self.category.blockSignals(False)
            self.target_names = {}
            if self.resource == 'presets':
                for group in ('products', 'addons'):
                    for row in self.client.list_records(group):
                        self.target_names[('product_id' if group == 'products' else 'addon_id', row['id'])] = row['name']
            if self.resource == 'settings':
                by_key = {r['key']: r for r in records}
                records = [by_key.get(key, {'key': key, 'value': value}) for key, value in
                           [('restaurant_name', ''), ('business_day_start', '06:00'), ('timezone', 'Asia/Tashkent')]]
            self.records = records
            self.render()
            self.notice.setText('Yozuvni tanlab tahrirlang. O‘chirish o‘rniga nofaol qilish ishlatiladi.')
            if self.resource == 'settings':
                self.notice.setText('06:00 va Asia/Tashkent — tasdiqlangan backend qoidalari. Maxfiy kalitlar bu yerda yo‘q.')
        except Exception as error:
            self.on_error(error)

    def render(self):
        self.rows.clear()
        for record in self.records:
            if self.resource == 'products' and self.category.currentData() is not None and record['category_id'] != self.category.currentData():
                continue
            active = 'Faol' if record.get('is_active', True) else 'Nofaol'
            text = record.get('name', record.get('key', ''))
            if self.resource == 'products':
                price = 'Qo‘lda narx' if record['allows_manual_price'] else format_money(record['base_price'])
                text += f" · {record['unit_type']} · {price}"
            elif self.resource == 'addons':
                text += ' · Qo‘lda narx' if record['allows_manual_price'] else ' · ' + format_money(record['base_price'])
            elif self.resource == 'presets':
                field = 'product_id' if record.get('product_id') else 'addon_id'
                text = f"{self.target_names.get((field, record[field]), 'Noma’lum')} · {format_money(record['amount'])} · Tartib: {record['sort_order']}"
            elif self.resource == 'users':
                text += f" · {record['username']} · {record['role']}"
            elif self.resource == 'workers':
                text += f" · {record['phone']}"
            elif self.resource == 'printers':
                text += f" · {record['terminal_name']} · {record['connection_type']}\nPOS_PRINTER_ID={record['id']} · {record['address']}"
            elif self.resource == 'settings':
                text += f" = {record['value']}"
            row = QListWidgetItem(text + (f'\n{active}' if self.resource != 'settings' else ''))
            row.setData(Qt.ItemDataRole.UserRole, record)
            row.setSizeHint(QSize(0, 90))
            self.rows.addItem(row)

    def edit(self, new=False):
        original = None if new else self.selected()
        if not new and original is None:
            return
        try:
            dialog = RecordEditor(self.resource, self.client, original, self.on_error, self)
            if dialog.exec():
                self.load()
                self.notice.setText('Muvaffaqiyatli saqlandi.')
        except Exception as error:
            self.on_error(error)

    def osh_prices(self):
        product = self.selected()
        if not product or menu_name(product['name']) != 'osh':
            QMessageBox.information(self, 'Osh', 'Ro‘yxatdan Oshni tanlang')
            return
        values = {}
        for option in product.get('price_options', []):
            if option['name'] in {'0.5 porsiya', '1 porsiya'} and option['is_active']:
                values['half_price' if option['name'] == '0.5 porsiya' else 'full_price'] = option['price']
        fields = [('half_price', '0.5 porsiya', 'money'), ('full_price', '1 porsiya', 'money')]
        def save(data):
            if not data['half_price'] or not data['full_price']:
                raise ValueError('Ikkala porsiya narxi ham musbat bo‘lishi kerak')
            self.client.save_osh_prices(product['id'], **data)
        dialog = Editor('OSH — porsiya narxlari', fields, values, save, self.on_error, self)
        if dialog.exec():
            self.load()
            self.notice.setText('Ikkala Osh porsiya narxi saqlandi. Eski variantlar nofaol saqlandi.')

    def links(self):
        product = self.selected()
        if not product:
            return
        try:
            addons = self.client.list_records('addons')
            labels = [f"{a['name']} ({'faol' if a['is_active'] else 'nofaol'})" for a in addons]
            choice, accepted = QInputDialog.getItem(self, 'Qo‘shimcha', 'Bog‘lanadigan qo‘shimcha:', labels, editable=False)
            if not accepted:
                return
            addon = addons[labels.index(choice)]
            link = next((l for l in self.client.links(product['id']) if l['addon_id'] == addon['id']), {'is_active': False, 'is_required': False})
            dialog = Editor(f"{product['name']} + {addon['name']}", [('is_active', 'Bog‘lanish faol', 'bool'), ('is_required', 'Majburiy', 'bool')],
                            link, lambda data: self.client.set_link(product['id'], addon['id'], data['is_active'], data['is_required']), self.on_error, self)
            if dialog.exec():
                self.load()
        except Exception as error:
            self.on_error(error)


class Dashboard(QWidget):
    def __init__(self, client, on_error, parent=None):
        super().__init__(parent)
        self.client, self.on_error = client, on_error
        layout = QVBoxLayout(self)
        self.summary = QLabel('Dashboard')
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet('font-size: 24px; padding: 24px;')
        layout.addWidget(self.summary)
        button = QPushButton('YANGILASH')
        button.clicked.connect(self.load)
        layout.addWidget(button)
        layout.addStretch()

    def load(self):
        try:
            self.client.get('/health')
            lines = ['Backend: ulangan']
            for resource, title in [('categories', 'Faol kategoriyalar'), ('products', 'Faol mahsulotlar'), ('workers', 'Faol yetkazib beruvchilar'),
                                    ('users', 'Faol foydalanuvchilar'), ('printers', 'Faol printerlar')]:
                rows = self.client.list_records(resource)
                lines.append(f"{title}: {sum(bool(r.get('is_active', True)) for r in rows)}")
                if resource == 'users':
                    lines.append(f"Faol kassirlar: {sum(r['role'] == 'CASHIER' and r['is_active'] for r in rows)}")
            self.summary.setText('\n\n'.join(lines))
        except Exception as error:
            self.summary.setText('Backend: ma’lumot yuklanmadi')
            self.on_error(error)
