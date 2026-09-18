from PySide6.QtCore import Qt, QSize, QDate
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
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()

        title = QLabel(TITLES[resource])
        title.setObjectName("pageTitle")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        header.addWidget(title)

        header.addStretch()

        layout.addLayout(header)
        if resource in {'products', 'categories', 'addons', 'presets'}:
            sections = QHBoxLayout()
            # Owner-facing menu intentionally exposes only two simple sections.
            for key, title in [
                ('products', 'MAHSULOTLAR'),
                ('categories', 'GURUHLAR'),
            ]:
                button = QPushButton(title)
                button.setMinimumHeight(52)
                button.setCheckable(True)
                button.setChecked(resource == key)
                button.clicked.connect(
                    lambda _=False, k=key:
                    self.window().navigate(k)
                    if hasattr(self.window(), 'navigate')
                    else None
                )
                sections.addWidget(button)
            layout.addLayout(sections)
        self.category = QComboBox()
        self.category.setMinimumHeight(50)
        self.category.addItem('Barcha menyu bo‘limlari', None)
        self.category.currentIndexChanged.connect(self.render)
        self.category.setVisible(resource == 'products')
        layout.addWidget(self.category)
        self.rows = QListWidget()
        self.rows.setObjectName("adminResourceList")
        self.rows.setIconSize(QSize(82, 62))
        self.rows.setWordWrap(True)
        self.rows.setSpacing(4)
        self.rows.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.rows.itemDoubleClicked.connect(lambda _: self.edit())
        layout.addWidget(self.rows)
        actions = QHBoxLayout()
        add_label = {
            'products': '+ YANGI MAHSULOT',
            'categories': '+ YANGI GURUH',
            'workers': '+ YANGI YETKAZIB BERUVCHI',
            'users': '+ YANGI KASSIR',
            'printers': '+ YANGI PRINTER',
        }.get(resource, '+ QO‘SHISH')

        self.add_button = QPushButton(add_label)
        self.add_button.setProperty("primary", True)
        self.add_button.setVisible(resource != 'settings')
        self.add_button.clicked.connect(lambda: self.edit(new=True))
        self.edit_button = QPushButton('TANLANGANNI TAHRIRLASH')
        self.edit_button.clicked.connect(lambda: self.edit())
        refresh = QPushButton('↻ YANGILASH')
        refresh.clicked.connect(self.load)
        for button in (self.add_button, self.edit_button, refresh):
            button.setMinimumHeight(54)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        if resource == 'products':
            extra = QHBoxLayout()
            osh = QPushButton('PORSIYA / VARIANTLAR')
            osh.setMinimumHeight(52)
            osh.clicked.connect(self.portions)
            links = QPushButton('OSH QO‘SHIMCHALARINI SOZLASH')
            links.setMinimumHeight(52)
            links.clicked.connect(self.links)
            extra.addWidget(osh)
            extra.addWidget(links)
            layout.addLayout(extra)
            prepare = QPushButton('MENYUDAGI YETISHMAYOTGANLARNI TAYYORLASH')
            prepare.setMinimumHeight(52)
            prepare.clicked.connect(self.prepare_menu)
            layout.addWidget(prepare)
        if resource in {'products', 'addons'}:
            quick = QPushButton('4 TA TEZKOR NARXNI SOZLASH')
            quick.setMinimumHeight(52)
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
                self.category.addItem('Barcha menyu bo‘limlari', None)
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
            self.notice.setText(
                'Kerakli yozuvni tanlang. '
                'O‘chirish o‘rniga Faol / Nofaol holati ishlatiladi.'
            )
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
                if menu_name(record['name']) in {'gosht', "go'sht"}:
                    text += '\n4 ta tezkor narx + boshqa narx (min 5 000 so‘m)'
                else:
                    text += '\n' + format_money(record['base_price']) + ' / dona'
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
            row.setSizeHint(
                QSize(
                    0,
                    92 if self.resource == 'products' else 74,
                )
            )
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

        if menu_name(product.get("name", "")) != "osh":
            QMessageBox.information(
                self,
                "Osh qo‘shimchalari",
                "Qo‘shimchalar faqat Osh uchun sozlanadi.",
            )
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

        self.client = client
        self.on_error = on_error

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        top = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        title.setStyleSheet(
            "font-size: 26px; font-weight: 800;"
        )
        title_box.addWidget(title)

        self.summary = QLabel(
            "Server holati tekshirilmoqda..."
        )
        self.summary.setWordWrap(True)
        self.summary.setObjectName("dashboardStatus")
        title_box.addWidget(self.summary)

        top.addLayout(title_box)
        top.addStretch()

        refresh = QPushButton("↻ YANGILASH")
        refresh.setMinimumHeight(52)
        refresh.setMinimumWidth(150)
        refresh.clicked.connect(self.load)
        top.addWidget(refresh)

        layout.addLayout(top)

        grid = QGridLayout()
        grid.setSpacing(12)

        self.cards = {}

        cards = [
            ("sales", "Bugungi savdo"),
            ("orders", "Buyurtmalar"),
            ("delivery", "Yetkazib berish"),
            ("cashiers", "Kassirlar"),
        ]

        for index, (key, title_text) in enumerate(cards):
            card = QWidget()
            card.setObjectName("summaryCard")
            card.setMinimumHeight(118)

            box = QVBoxLayout(card)
            box.setContentsMargins(18, 16, 18, 16)
            box.setSpacing(6)

            label = QLabel(title_text)
            label.setObjectName("summaryTitle")
            box.addWidget(label)

            value = QLabel("—")
            value.setObjectName("dashboardValue")
            value.setStyleSheet(
                "font-size: 30px; font-weight: 800;"
            )
            box.addWidget(value)

            grid.addWidget(
                card,
                index // 2,
                index % 2,
            )

            self.cards[key] = value

        layout.addLayout(grid)

        catalog_title = QLabel("MENYU HOLATI")
        catalog_title.setObjectName("sectionTitle")
        catalog_title.setStyleSheet(
            "font-size: 16px; font-weight: 700;"
        )
        layout.addWidget(catalog_title)

        self.catalog = QListWidget()
        self.catalog.setObjectName("dashboardCatalog")
        self.catalog.setWordWrap(True)
        self.catalog.setSpacing(3)
        self.catalog.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.catalog, 1)

    def load(self):
        try:
            self.client.get("/health")

            products = self.client.list_records("products")
            users = self.client.list_records("users")
            categories = self.client.list_records("categories")

            active_products = sum(
                bool(row.get("is_active", True))
                for row in products
            )

            active_cashiers = sum(
                row.get("role") == "CASHIER"
                and bool(row.get("is_active", True))
                for row in users
            )

            today = QDate.currentDate().toString(
                "yyyy-MM-dd"
            )

            report = self.client.get(
                "/api/admin/reports/daily"
                f"?period=kunlik&business_date={today}"
            )

            total_sales = report.get(
                "total_paid_amount",
                0,
            )

            total_orders = report.get(
                "total_order_count",
                0,
            )

            delivery_sales = (
                report.get("by_order_type", {})
                .get("DELIVERY", 0)
            )

            self.cards["sales"].setText(
                format_money(total_sales)
            )

            self.cards["orders"].setText(
                f"{total_orders} ta"
            )

            self.cards["delivery"].setText(
                format_money(delivery_sales)
            )

            self.cards["cashiers"].setText(
                f"{active_cashiers} faol"
            )

            self.summary.setText(
                "Backend: ulangan"
                f"   ·   {active_products} faol mahsulot"
                f"   ·   {active_cashiers} faol kassir"
            )

            self.catalog.clear()

            for category in categories:
                if not category.get("is_active", True):
                    continue

                header = QListWidgetItem(
                    category["name"].upper()
                )
                header.setSizeHint(QSize(0, 40))
                self.catalog.addItem(header)

                for product in products:
                    if (
                        product.get("category_id")
                        != category["id"]
                    ):
                        continue

                    status = (
                        "Sotuvda"
                        if product.get("is_active", True)
                        else "O‘chirilgan"
                    )

                    item = QListWidgetItem(
                        f"{product['name']}  ·  {status}"
                    )
                    item.setSizeHint(QSize(0, 48))
                    self.catalog.addItem(item)

        except Exception as error:
            self.summary.setText(
                "● Server yoki ma’lumotlar bilan "
                "ulanishda muammo"
            )
            self.on_error(error)
