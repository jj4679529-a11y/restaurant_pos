from PySide6.QtWidgets import QScroller
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
                button.setMinimumHeight(60)
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

        QScroller.grabGesture(
            self.rows.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
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

        self.active_button = QPushButton(
            'FAOL / NOFAOL'
        )
        self.active_button.setVisible(
            resource == 'products'
        )
        self.active_button.clicked.connect(
            self.toggle_product_active
        )

        self.delete_button = QPushButton(
            'BUTUNLAY O‘CHIRISH'
        )
        self.delete_button.setVisible(
            resource == 'products'
        )
        self.delete_button.clicked.connect(
            self.delete_product
        )

        refresh = QPushButton('↻ YANGILASH')
        refresh.clicked.connect(self.load)
        for button in (
            self.add_button,
            self.edit_button,
            self.active_button,
            self.delete_button,
            refresh,
        ):
            button.setMinimumHeight(54)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
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
                try:
                    self.menu_addons = self.client.list_records(
                        "addons"
                    )
                except Exception:
                    self.menu_addons = []

                selected = self.category.currentData()
                self.category.blockSignals(True)
                self.category.clear()
                self.category.addItem('Barcha menyu bo‘limlari', None)
                categories = self.client.list_records('categories')
                self.category_names = {
                    row['id']: row['name']
                    for row in categories
                }

                for row in categories:
                    self.category.addItem(
                        row['name'],
                        row['id'],
                    )
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
                unit_labels = {
                    'PIECE': 'Dona',
                    'PORTION': 'Porsiya',
                    'LITER': 'Litr',
                    'AMOUNT': 'Kassir qo‘lda narx kiritadi',
                }

                unit = unit_labels.get(
                    record.get('unit_type'),
                    '—',
                )

                if menu_name(
                    record.get("name", "")
                ) == "osh":
                    option_prices = {
                        option.get("name"):
                        option.get("price", 0)
                        for option in record.get(
                            "price_options",
                            []
                        )
                        if option.get(
                            "is_active",
                            True,
                        )
                    }

                    half = option_prices.get(
                        "0.5 porsiya",
                        0,
                    )
                    full = option_prices.get(
                        "1 porsiya",
                        0,
                    )

                    price = (
                        "0.5: "
                        + format_money(half)
                        + "   ·   1: "
                        + format_money(full)
                    )

                elif record.get(
                    'allows_manual_price',
                    False,
                ):
                    price = 'Kassir kiritadi'

                else:
                    price = format_money(
                        record.get(
                            'base_price',
                            0,
                        )
                    )

                category_name = getattr(
                    self,
                    'category_names',
                    {},
                ).get(
                    record.get('category_id'),
                    '—',
                )

                text = (
                    f"{record['name']}\n"
                    f"Narxi: {price}\n"
                    f"Menyu bo‘limi: {category_name}"
                    f"   ·   Sotish usuli: {unit}"
                )
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
                    124 if self.resource == 'products' else 88,
                )
            )
            if self.resource == 'products':
                row.setIcon(QIcon(product_pixmap(self.client.load_image(record.get('image_path')))))
            self.rows.addItem(row)

        # Osh qo‘shimchalari ham egasi uchun
        # MAHSULOTLAR ro‘yxatining bir qismi.
        if self.resource == "products":
            for addon in getattr(
                self,
                "menu_addons",
                [],
            ):
                key = menu_name(
                    addon.get("name", "")
                )

                if key not in {
                    "tuxum",
                    "tuxum1",
                    "bedanatuxum",
                    "qazi",
                    "gosht",
                }:
                    continue

                item_record = dict(addon)
                item_record["_strict_resource"] = "addons"

                if addon.get(
                    "allows_manual_price",
                    False,
                ):
                    price = "Kassir kiritadi"
                    method = (
                        "Kassir qo‘lda narx kiritadi"
                    )
                else:
                    price = format_money(
                        addon.get(
                            "base_price",
                            0,
                        )
                    )
                    method = "Dona"

                active = (
                    "Faol"
                    if addon.get(
                        "is_active",
                        True,
                    )
                    else "Nofaol"
                )

                text = (
                    f"{addon['name']}\n"
                    f"Narxi: {price}\n"
                    "Menyu bo‘limi: Osh qo‘shimchalari"
                    f"   ·   Sotish usuli: {method}\n"
                    f"{active}"
                )

                row = QListWidgetItem(text)
                row.setData(
                    Qt.ItemDataRole.UserRole,
                    item_record,
                )
                row.setSizeHint(
                    QSize(0, 108)
                )

                self.rows.addItem(row)

    def edit(self, new=False):
        if new and self.resource == "products":
            from app.ui.admin.menu_wizard import StrictMenuWizard

            wizard = StrictMenuWizard(
                self.client,
                self.on_error,
                self,
            )

            if wizard.run():
                self.load()
                self.notice.setText(
                    "Muvaffaqiyatli saqlandi."
                )

            return

        original = None if new else self.selected()

        if not new and original is None:
            return

        if (
            self.resource == "products"
            and original
        ):
            try:
                from app.ui.admin.menu_wizard import (
                    edit_strict_record,
                )

                if edit_strict_record(
                    self.client,
                    original,
                    self.on_error,
                    self,
                ):
                    self.load()
                    self.notice.setText(
                        "Muvaffaqiyatli saqlandi."
                    )

            except Exception as error:
                self.on_error(error)

            return

        try:
            dialog = RecordEditor(
                self.resource,
                self.client,
                original,
                self.on_error,
                self,
            )

            if dialog.exec():
                self.load()
                self.notice.setText(
                    "Muvaffaqiyatli saqlandi."
                )

        except Exception as error:
            self.on_error(error)

    def toggle_product_active(self):
        product = self.selected()

        if not product:
            QMessageBox.information(
                self,
                "Mahsulot",
                "Avval mahsulotni tanlang.",
            )
            return

        if product.get("_strict_resource") == "addons":
            QMessageBox.information(
                self,
                "Qo‘shimcha",
                "Bu Osh qo‘shimchasi. Uni qo‘shimchalar sozlamasidan boshqaring.",
            )
            return

        currently_active = product.get(
            "is_active",
            True,
        )

        action = (
            "nofaol qilish"
            if currently_active
            else "faollashtirish"
        )

        answer = QMessageBox.question(
            self,
            "Mahsulot holati",
            f"{product['name']} mahsulotini {action}?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.client.save_record(
                "products",
                {
                    "is_active": not currently_active,
                },
                product,
            )

            self.load()

            self.notice.setText(
                "Mahsulot "
                + (
                    "nofaol qilindi."
                    if currently_active
                    else "faollashtirildi."
                )
            )

        except Exception as error:
            self.on_error(error)


    def delete_product(self):
        product = self.selected()

        if not product:
            QMessageBox.information(
                self,
                "Mahsulot",
                "Avval mahsulotni tanlang.",
            )
            return

        if product.get("_strict_resource") == "addons":
            QMessageBox.information(
                self,
                "Qo‘shimcha",
                "Osh qo‘shimchasini bu tugma orqali o‘chirib bo‘lmaydi.",
            )
            return

        answer = QMessageBox.warning(
            self,
            "Butunlay o‘chirish",
            (
                f"{product['name']} mahsuloti butunlay o‘chirilsinmi?\n\n"
                "Bu amalni ortga qaytarib bo‘lmaydi.\n"
                "Agar mahsulot oldingi buyurtmalarda ishlatilgan bo‘lsa, "
                "tizim o‘chirishni bloklaydi."
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.client.delete_product(
                product["id"]
            )

            self.load()

            self.notice.setText(
                "Mahsulot butunlay o‘chirildi."
            )

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
        refresh.setMinimumHeight(64)
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
        self.catalog.setSpacing(6)
        self.catalog.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        QScroller.grabGesture(
            self.catalog.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
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
