from decimal import Decimal
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QButtonGroup, QDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.state import CartAddOn, CartItem, CartValidationError, format_money


class ProductDialog(QDialog):
    def __init__(self, product, existing=None, parent=None):
        super().__init__(parent)
        self.product = product
        self.is_osh = product['name'].strip().casefold() == 'osh'
        self.quantity = existing.quantity if existing else Decimal(1)
        self.option = None
        self.manual_price = existing.manual_price if existing else None
        if self.is_osh:
            self.manual_price = None
        self.addons = {a.addon_id: a for a in existing.addons} if existing else {}
        self.result_item = None
        self.setWindowTitle(product["name"])
        self.resize(740, 660)
        layout = QVBoxLayout(self)
        title = QLabel(product["name"])
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        # Keep labels readable under macOS dark-mode native scroll palettes.
        content.setStyleSheet('background: #f3f5f2;')
        body = QVBoxLayout(content)
        options = [o for o in product.get("price_options", []) if o.get("is_active", True)]
        if self.is_osh:
            options = [o for o in options if str(o.get('name', '')).strip() in {'0.5 porsiya', '1 porsiya'}
                       and Decimal(str(o.get('quantity', 0))) in {Decimal('0.5'), Decimal('1')} and o.get('price', 0) > 0]
            options.sort(key=lambda o: Decimal(str(o['quantity'])))
            # Ambiguous/missing configuration must not offer a price fallback.
            if len(options) != 2 or {Decimal(str(o['quantity'])) for o in options} != {Decimal('0.5'), Decimal('1')}:
                options = []
                body.addWidget(QLabel('Osh porsiya narxlari sozlanmagan. Administratorga murojaat qiling.'))
        self.options_group = QButtonGroup(self)
        if options:
            body.addWidget(QLabel("Porsiya / variant"))
        for option in options:
            button = QPushButton(f"{option['name']} — {format_money(option['price'])}")
            button.setCheckable(True)
            self.options_group.addButton(button)
            body.addWidget(button)
            button.clicked.connect(lambda _=False, value=option: self._option(value))
            if existing and option["id"] == existing.selected_price_option_id:
                button.setChecked(True)
                self.option = option
        if product.get("allows_manual_price") and not self.is_osh:
            button = QPushButton("NARXNI TANLASH")
            button.clicked.connect(self._product_price)
            body.addWidget(button)
        body.addWidget(QLabel("Tanlangan porsiya / mahsulot soni"))
        self.count_label = QLabel(format(self.quantity, "f"))
        body.addLayout(self._stepper(self.count_label, self._count))
        if product.get("available_addons"):
            body.addWidget(QLabel("Qo‘shimchalar — shu qatordagi jami soni"))
        self.addon_labels = {}
        for addon in product.get("available_addons", []):
            if not addon.get("is_active", True) or not addon.get("relationship_active", True):
                continue
            row = QHBoxLayout()
            row.addWidget(QLabel(addon["name"]), 1)
            selected = self.addons.get(addon["id"])
            if addon.get("is_required") and selected is None and not addon.get("allows_manual_price") and addon["base_price"] > 0:
                selected = CartAddOn(addon["id"], addon["name"], Decimal(1), addon["base_price"])
                self.addons[addon["id"]] = selected
            if addon.get("allows_manual_price"):
                presets = [p for p in addon.get('manual_price_presets', []) if p.get('is_active', True)]
                body.addWidget(QLabel(addon['name']))
                grid = QGridLayout()
                for index, preset in enumerate(presets):
                    button = QPushButton(format_money(preset['amount']))
                    button.clicked.connect(lambda _=False, a=addon, amount=preset['amount']: self._set_manual_addon(a, amount))
                    grid.addWidget(button, index // 3, index % 3)
                body.addLayout(grid)
                if not presets:
                    body.addWidget(QLabel('Tezkor narxlar sozlanmagan'))
                add = QPushButton("BOSHQA NARX")
                add.clicked.connect(lambda _=False, value=addon: self._manual_addon(value))
                remove = QPushButton("×")
                remove.setFixedWidth(54)
                remove.clicked.connect(lambda _=False, value=addon: self._remove_addon(value))
                row.addWidget(add)
                row.addWidget(remove)
                amount = QLabel(format_money(selected.unit_price) if selected else "—")
                self.addon_labels[addon["id"]] = amount
                row.addWidget(amount)
            else:
                row.addWidget(QLabel(format_money(addon["base_price"]) if addon["base_price"] > 0 else "Narx sozlanmagan"))
                count = QLabel(format(selected.quantity, "f") if selected else "0")
                self.addon_labels[addon["id"]] = count
                row.addLayout(self._stepper(count, lambda d, value=addon: self._addon_count(value, d)))
            body.addLayout(row)
        body.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.total = QLabel()
        self.total.setWordWrap(True)
        self.total.setObjectName("totalLabel")
        layout.addWidget(self.total)
        actions = QHBoxLayout()
        cancel = QPushButton("BEKOR QILISH")
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton("BUYURTMAGA QO‘SHISH" if existing is None else "SAQLASH")
        self.confirm.clicked.connect(self._accept_item)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        layout.addLayout(actions)
        self._refresh()

    def _stepper(self, label, action):
        row = QHBoxLayout()
        for text, delta in (("−", -1), ("+", 1)):
            button = QPushButton(text)
            button.setFixedWidth(58)
            button.clicked.connect(lambda _=False, value=delta: action(value))
            row.addWidget(button)
            if delta == -1:
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setMinimumWidth(42)
                row.addWidget(label)
        return row

    def _option(self, value):
        self.option = value
        self._refresh()

    def _count(self, delta):
        self.quantity = max(Decimal(1), self.quantity + delta)
        self.count_label.setText(format(self.quantity, "f"))
        self._refresh()

    def _product_price(self):
        if self.is_osh:
            return
        value = NumberDialog.money(self, self.product["name"], self.product.get("manual_price_presets", []), self.manual_price or 0)
        if value is not None:
            self.manual_price = value
            self._refresh()

    def _manual_addon(self, addon):
        existing = self.addons.get(addon["id"])
        value = NumberDialog.money(self, addon["name"], addon.get("manual_price_presets", []), existing.manual_price if existing else 0)
        if value is not None:
            self._set_manual_addon(addon, value)

    def _set_manual_addon(self, addon, value):
        self.addons[addon['id']] = CartAddOn(addon['id'], addon['name'], Decimal(1), value, value)
        self.addon_labels[addon['id']].setText(format_money(value))
        self._refresh()

    def _remove_addon(self, addon):
        if not addon.get("is_required"):
            self.addons.pop(addon["id"], None)
            self.addon_labels[addon["id"]].setText("—")
            self._refresh()

    def _addon_count(self, addon, delta):
        if addon["base_price"] <= 0:
            QMessageBox.warning(self, "Narx", "Narx sozlanmagan. Administratorga murojaat qiling.")
            return
        current = self.addons.get(addon["id"])
        quantity = max(Decimal(1 if addon.get("is_required") else 0), (current.quantity if current else Decimal(0)) + delta)
        if quantity:
            self.addons[addon["id"]] = CartAddOn(addon["id"], addon["name"], quantity, addon["base_price"])
        else:
            self.addons.pop(addon["id"], None)
        self.addon_labels[addon["id"]].setText(format(quantity, "f"))
        self._refresh()

    def _item(self):
        if self.is_osh and self.option is None:
            raise CartValidationError('Osh porsiyasini tanlang; narx sozlanmagan bo‘lsa Administratorga murojaat qiling')
        if any(o.get("is_active", True) for o in self.product.get("price_options", [])) and self.option is None:
            raise CartValidationError("Porsiyani tanlang")
        for addon in self.product.get("available_addons", []):
            if addon.get("is_required") and addon["id"] not in self.addons:
                raise CartValidationError(f"{addon['name']}ni tanlang")
        item = CartItem.from_catalog(self.product, self.quantity, self.option, self.manual_price, tuple(self.addons.values()))
        _ = item.total_price
        return item

    def _refresh(self):
        try:
            item = self._item()
        except CartValidationError as error:
            self.total.setText(str(error))
            self.confirm.setEnabled(False)
        else:
            self.total.setText(f"Jami: {format_money(item.total_price)}")
            self.confirm.setEnabled(True)

    def _accept_item(self):
        self.result_item = self._item()
        self.accept()

    @classmethod
    def choose(cls, product, existing=None, parent=None):
        dialog = cls(product, existing, parent)
        return dialog.result_item if dialog.exec() == QDialog.DialogCode.Accepted else None
