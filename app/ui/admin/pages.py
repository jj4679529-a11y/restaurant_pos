from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QComboBox, QInputDialog, QMessageBox

from app.ui.admin.forms import Editor, RecordEditor
from app.ui.admin.api import menu_name
from app.ui.state import format_money
from app.ui.widgets.product_card import product_pixmap

TITLES = {'categories': 'Menyu guruhlari', 'products': 'Menyu', 'addons': 'Qo‘shimchalar',
          'presets': 'Tezkor narxlar', 'workers': 'Yetkazib beruvchilar', 'users': 'Kassirlar',
          'printers': 'Printerlar', 'settings': 'Sozlamalar'}


class ResourcePage(QWidget):
    def __init__(self, resource, client, on_error, parent=None):
        super().__init__(parent)
        self.resource, self.client, self.on_error = resource, client, on_error
        self.records = []
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(TITLES[resource]))
        if resource in {'products', 'categories', 'addons', 'presets'}:
            sections = QHBoxLayout()
            # Owner-facing menu intentionally exposes only two simple sections.
            for key, title in [('products', 'Umumiy mahsulotlar'), ('categories', 'Guruhlar')]:
                button = QPushButton(title)
                button.clicked.connect(lambda _=False, k=key: self.window().navigate(k) if hasattr(self.window(), 'navigate') else None)
                sections.addWidget(button)
            layout.addLayout(sections)
        self.category = QComboBox()
        self.category.addItem('Barcha kategoriyalar', None)
        self.category.currentIndexChanged.connect(self.render)
        self.category.setVisible(resource == 'products')
        layout.addWidget(self.category)
        self.rows = QListWidget()
        self.rows.setIconSize(QSize(64, 40))
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
        actions.addStretch()
        layout.addLayout(actions)
        if resource == 'products':
            extra = QHBoxLayout()
            osh = QPushButton('PORSIYA / NON VARIANTLARI')
            osh.clicked.connect(self.portions)
            links = QPushButton('QO‘SHIMCHA BOG‘LASH / AJRATISH')
            links.clicked.connect(self.links)
            extra.addWidget(osh)
            extra.addWidget(links)
            layout.addLayout(extra)
            prepare = QPushButton('YAKUNIY MENYUNI TAYYORLASH')
            prepare.clicked.connect(self.prepare_menu)
            layout.addWidget(prepare)
        if resource in {'products', 'addons'}:
            quick = QPushButton('TEZKOR NARXLARNI SOZLASH')
            quick.clicked.connect(self.quick_prices)
            layout.addWidget(quick)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        if resource == 'settings':
            password = QPushButton('ADMIN PAROLINI O‘ZGARTIRISH')
            password.clicked.connect(self.change_password)
            layout.addWidget(password)

    def change_password(self):
        window = self.window()
        if not hasattr(window, 'session'):
            return
        user = window.session.user
        def save(data):
            if not data['password'].strip():
                raise ValueError('Yangi parolni kiriting')
            self.client.request('PATCH', f'/api/users/{user["id"]}', data)
        Editor('Admin paroli', [('password', 'Yangi parol', 'password')], {}, save, self.on_error, self).exec()

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
                self.notice.setText('Standart: 06:00, Asia/Tashkent. Sozlama yangi buyurtmalarga ta’sir qiladi; tarix o‘zgarmaydi.')
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
                price = 'Narxni kassir kiritadi' if record['allows_manual_price'] else format_money(record['base_price']) + ' / ' + {'PIECE': 'dona', 'PORTION': 'porsiya', 'LITER': 'litr', 'AMOUNT': 'summa'}.get(record['unit_type'], '')
                if menu_name(record['name']) == 'osh':
                    price = 'Admin belgilagan porsiyalar'
                text += f" · {price}"
            elif self.resource == 'addons':
                text += ' · Narxni kassir kiritadi' if record['allows_manual_price'] else ' · ' + format_money(record['base_price']) + ' / dona'
            elif self.resource == 'presets':
                field = 'product_id' if record.get('product_id') else 'addon_id'
                text = f"{self.target_names.get((field, record[field]), 'Noma’lum')} · {format_money(record['amount'])} · Tartib: {record['sort_order']}"
            elif self.resource == 'users':
                text += f" · {record['username']} · {record.get('phone') or ''} · " + ('Kassir' if record['role'] == 'CASHIER' else 'Administrator')
            elif self.resource == 'workers':
                text += f" · {record['phone']}"
            elif self.resource == 'printers':
                text += f" · {record['terminal_name']} · {record['connection_type']}\nPOS_PRINTER_ID={record['id']} · {record['address']}"
            elif self.resource == 'settings':
                text = {'restaurant_name': 'Restoran nomi', 'business_day_start': 'Ish kuni boshlanishi', 'timezone': 'Vaqt mintaqasi'}.get(record['key'], record['key']) + f" · {record['value']}"
            row = QListWidgetItem(text + (f'\n{active}' if self.resource != 'settings' else ''))
            row.setData(Qt.ItemDataRole.UserRole, record)
            row.setSizeHint(QSize(0, 64))
            if self.resource == 'products':
                row.setIcon(QIcon(product_pixmap(self.client.load_image(record.get('image_path')))))
            self.rows.addItem(row)

    def edit(self, new=False):
        original = None if new else self.selected()
        if not new and original is None:
            return
        if self.resource == 'products' and original and menu_name(original['name']) == 'osh':
            self.portions()
            return
        try:
            dialog = RecordEditor(self.resource, self.client, original, self.on_error, self)
            if dialog.exec():
                self.load()
                self.notice.setText('Muvaffaqiyatli saqlandi.')
        except Exception as error:
            self.on_error(error)

    def portions(self):
        from app.ui.admin.portions import PortionsDialog
        product = self.selected()
        if product:
            PortionsDialog(self.client, product, self.on_error, self).exec()
            self.load()

    def prepare_menu(self):
        if QMessageBox.question(self, 'Menyu', 'Yetishmayotgan menyuni qo‘shish? Narxlar saqlanadi; yangi narxlarni o‘zingiz kiriting.') != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.client.post('/api/admin/menu/prepare')
            self.load()
            self.notice.setText(result['message'])
        except Exception as error:
            self.on_error(error)

    def quick_prices(self):
        from app.ui.admin.menu_settings import QuickPricesDialog
        target = self.selected()
        if not target or not target.get('allows_manual_price'):
            QMessageBox.information(self, 'Tezkor narxlar', 'Narxini kassir kiritadigan mahsulot yoki qo‘shimchani tanlang.')
            return
        QuickPricesDialog(self.client, self.resource, target, self.on_error, self).exec()
        self.load()

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
        grid = QGridLayout()
        self.cards = {}
        for index, (key, title) in enumerate([('products', 'Mahsulotlar'), ('workers', 'Yetkazib beruvchilar'), ('users', 'Kassirlar')]):
            card = QWidget()
            card.setObjectName('summaryCard')
            box = QVBoxLayout(card)
            box.addWidget(QLabel(title))
            value = QLabel('—')
            value.setObjectName('dialogTitle')
            box.addWidget(value)
            grid.addWidget(card, 0, index)
            self.cards[key] = value
        layout.addLayout(grid)
        button = QPushButton('YANGILASH')
        button.clicked.connect(self.load)
        layout.addWidget(button)
        self.catalog = QListWidget()
        self.catalog.setWordWrap(True)
        layout.addWidget(self.catalog, 1)

    def load(self):
        try:
            self.client.get('/health')
            lines = ['Backend: ulangan']
            for resource, title in [('categories', 'Faol kategoriyalar'), ('products', 'Faol mahsulotlar'), ('workers', 'Faol yetkazib beruvchilar'),
                                    ('users', 'Faol foydalanuvchilar'), ('printers', 'Faol printerlar')]:
                rows = self.client.list_records(resource)
                if resource in self.cards:
                    self.cards[resource].setText(str(sum(r.get('is_active', True) and (resource != 'users' or r['role'] == 'CASHIER') for r in rows)))
                lines.append(f"{title}: {sum(bool(r.get('is_active', True)) for r in rows)}")
                if resource == 'users':
                    lines.append(f"Faol kassirlar: {sum(r['role'] == 'CASHIER' and r['is_active'] for r in rows)}")
            self.summary.setText(lines[0] + '\n' + next(line for line in lines if line.startswith('Faol printerlar')))
            self.catalog.clear()
            products = self.client.list_records('products')
            for category in self.client.list_records('categories'):
                self.catalog.addItem('— ' + category['name'].upper() + ' —')
                for product in products:
                    if product['category_id'] == category['id']:
                        self.catalog.addItem(product['name'] + (' · Nofaol' if not product['is_active'] else ''))
        except Exception as error:
            self.summary.setText('Backend: ma’lumot yuklanmadi')
            self.on_error(error)
