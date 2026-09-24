from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QScroller,
    QVBoxLayout,
    QWidget,
)

from app.menu_rules import PIECE_DRINKS, menu_key
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.dialogs.volume_dialog import VolumeDialog
from app.ui.state import (
    CartAddOn,
    CartItem,
    CartValidationError,
    format_money,
    format_quantity,
)


def _key(value):
    return menu_key(value or "")


def _is_osh(value):
    key = _key(value)
    return key == "osh" or key.endswith(" osh")


def _is_jizz(value):
    return _key(value) == "jizz"


def _is_gosht(value):
    return _key(value) == "gosht"



def _unique_available_addons(product):
    """Return one visible active addon per id/name.

    Old databases may contain logically duplicated addons with different IDs.
    Cashier UI must still show only one Tuxum/Qazi/Go'sht row.
    """
    result = []
    seen_ids = set()
    seen_names = set()

    for addon in product.get("available_addons", []):
        if not addon.get("is_active", True):
            continue

        if not addon.get("relationship_active", True):
            continue

        addon_id = addon.get("id")

        normalized_name = "".join(
            char
            for char in str(addon.get("name", "")).casefold()
            if char.isalnum()
        )

        if addon_id in seen_ids:
            continue

        if normalized_name and normalized_name in seen_names:
            continue

        seen_ids.add(addon_id)

        if normalized_name:
            seen_names.add(normalized_name)

        result.append(addon)

    return result


class ProductDialog(QDialog):
    def __init__(self, product, existing=None, parent=None):
        super().__init__(parent)

        self.product = product
        self.is_osh = _is_osh(product.get("name", ""))
        self.is_jizz = _is_jizz(product.get("name", ""))

        self.is_liter = (
            product.get("unit_type") == "LITER"
            and _key(product.get("name", "")) not in PIECE_DRINKS
        )

        self.quantity = existing.quantity if existing else Decimal(1)
        self.option = None
        self.manual_price = existing.manual_price if existing else None

        if self.is_osh:
            self.manual_price = None

        self.addons = (
            {addon.addon_id: addon for addon in existing.addons}
            if existing
            else {}
        )

        self.result_item = None

        self.setWindowTitle(product["name"])
        self.resize(760, 680)

        layout = QVBoxLayout(self)

        title = QLabel(product["name"])
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        QScroller.grabGesture(
            self.scroll.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        content = QWidget()
        body = QVBoxLayout(content)
        body.setSpacing(12)

        options = [
            option
            for option in product.get("price_options", [])
            if option.get("is_active", True)
        ]

        self.has_configured_options = bool(options)

        if self.is_osh:
            options = [
                option
                for option in options
                if Decimal(str(option.get("quantity", 0))) > 0
                and option.get("price", 0) > 0
            ]

            options.sort(
                key=lambda option: Decimal(
                    str(option.get("quantity", 0))
                )
            )

            if not options:
                body.addWidget(
                    QLabel(
                        "Osh porsiya narxlari sozlanmagan. "
                        "Administratorga murojaat qiling."
                    )
                )

        self.options_group = QButtonGroup(self)

        if options:
            body.addWidget(QLabel("Porsiya / variant"))

        for option in options:
            button = QPushButton(
                f"{option['name']} — {format_money(option['price'])}"
            )
            button.setMinimumHeight(56)
            button.setCheckable(True)

            self.options_group.addButton(button)
            body.addWidget(button)

            button.clicked.connect(
                lambda _=False, value=option: self._option(value)
            )

            if (
                existing
                and option["id"] == existing.selected_price_option_id
            ):
                button.setChecked(True)
                self.option = option

        if self.is_jizz:
            body.addWidget(QLabel("Tezkor narx"))

            grid = QGridLayout()

            presets = [
                preset
                for preset in product.get(
                    "manual_price_presets", []
                )
                if preset.get("is_active", True)
                and preset.get("amount", 0) > 0
            ][:4]

            for index, preset in enumerate(presets):
                choice = QPushButton(
                    format_money(preset["amount"])
                )
                choice.setMinimumHeight(56)

                choice.clicked.connect(
                    lambda _=False,
                    amount=preset["amount"]:
                    self._set_product_price(amount)
                )

                grid.addWidget(
                    choice,
                    index // 2,
                    index % 2,
                )

            body.addLayout(grid)

            other_price = QPushButton("BOSHQA NARX")
            other_price.setMinimumHeight(56)
            other_price.clicked.connect(self._product_price)

            body.addWidget(other_price)

        # One logical addon must appear only once even when an old DB
        # contains duplicate rows with different IDs.
        available_addons = _unique_available_addons(product)

        if available_addons:
            body.addWidget(QLabel("Qo‘shimchalar"))

        self.addon_labels = {}

        for addon in available_addons:
            row = QHBoxLayout()

            name_label = QLabel(addon["name"])
            name_label.setWordWrap(True)

            row.addWidget(name_label, 1)

            selected = self.addons.get(addon["id"])

            if (
                addon.get("is_required")
                and selected is None
                and not _is_gosht(addon["name"])
                and addon.get("base_price", 0) > 0
            ):
                selected = CartAddOn(
                    addon["id"],
                    addon["name"],
                    Decimal(1),
                    addon["base_price"],
                )

                self.addons[addon["id"]] = selected

            if _is_gosht(addon["name"]):
                presets = [
                    preset
                    for preset in addon.get(
                        "manual_price_presets", []
                    )
                    if preset.get("is_active", True)
                    and preset.get("amount", 0) >= 5000
                ][:4]

                grid = QGridLayout()

                for index, preset in enumerate(presets):
                    button = QPushButton(
                        format_money(preset["amount"])
                    )
                    button.setMinimumHeight(56)

                    button.clicked.connect(
                        lambda _=False,
                        current=addon,
                        amount=preset["amount"]:
                        self._set_manual_addon(
                            current,
                            amount,
                        )
                    )

                    grid.addWidget(
                        button,
                        index // 2,
                        index % 2,
                    )

                body.addLayout(grid)

                if not presets:
                    body.addWidget(
                        QLabel(
                            "Tezkor narxlar sozlanmagan"
                        )
                    )

                custom_price = QPushButton(
                    "BOSHQA NARX"
                )
                custom_price.setMinimumHeight(56)

                custom_price.clicked.connect(
                    lambda _=False,
                    value=addon:
                    self._manual_addon(value)
                )

                remove = QPushButton(
                    "OLIB TASHLASH"
                )
                remove.setMinimumHeight(56)

                remove.clicked.connect(
                    lambda _=False,
                    value=addon:
                    self._remove_addon(value)
                )

                row.addWidget(custom_price)
                row.addWidget(remove)

                amount_label = QLabel(
                    format_money(selected.unit_price)
                    if selected
                    else "—"
                )

                self.addon_labels[
                    addon["id"]
                ] = amount_label

                row.addWidget(amount_label)

            else:
                price = addon.get("base_price", 0)

                row.addWidget(
                    QLabel(
                        format_money(price)
                        if price > 0
                        else "Narx sozlanmagan"
                    )
                )

                count = QLabel(
                    format_quantity(
                        selected.quantity
                    )
                    if selected
                    else "0"
                )

                count.setObjectName("quantityValue")
                count.setMinimumSize(84, 58)

                count.setAlignment(
                    Qt.AlignmentFlag.AlignCenter
                )

                self.addon_labels[
                    addon["id"]
                ] = count

                row.addLayout(
                    self._stepper(
                        count,
                        lambda delta,
                        value=addon:
                        self._addon_count(
                            value,
                            delta,
                        ),
                    )
                )

            body.addLayout(row)


        self.count_label = QLabel(
            format_quantity(self.quantity)
        )
        self.count_label.setObjectName("quantityValue")
        self.count_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.count_label.setMinimumSize(100, 64)

        if self.is_liter and not self.has_configured_options:
            body.addWidget(
                QLabel(
                    "1 litr narxi: "
                    + format_money(
                        product.get("base_price", 0)
                    )
                )
            )

            body.addWidget(QLabel("Hajm"))

            volumes = QHBoxLayout()
            self.volume_group = QButtonGroup(self)

            for value in ("0.5", "1", "1.5", "2"):
                button = QPushButton(value + " L")
                button.setMinimumHeight(56)
                button.setCheckable(True)

                button.setChecked(
                    self.quantity == Decimal(value)
                )

                self.volume_group.addButton(button)

                button.clicked.connect(
                    lambda _=False,
                    amount=Decimal(value):
                    self._volume(amount)
                )

                volumes.addWidget(button)

            body.addLayout(volumes)

            custom = QPushButton("BOSHQA HAJM")
            custom.setMinimumHeight(56)
            custom.clicked.connect(self._custom_volume)

            body.addWidget(custom)

            self.count_label.setText(
                format_quantity(self.quantity) + " L"
            )

            body.addWidget(self.count_label)

        else:
            body.addWidget(QLabel("Mahsulot soni"))

            body.addLayout(
                self._stepper(
                    self.count_label,
                    self._count,
                )
            )

        body.addStretch()

        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)

        self.total = QLabel()
        self.total.setWordWrap(True)
        self.total.setObjectName("totalLabel")

        layout.addWidget(self.total)

        actions = QHBoxLayout()

        cancel = QPushButton("BEKOR QILISH")
        cancel.setMinimumHeight(60)
        cancel.clicked.connect(self.reject)

        self.confirm = QPushButton(
            "BUYURTMAGA QO‘SHISH"
            if existing is None
            else "SAQLASH"
        )

        self.confirm.setMinimumHeight(60)
        self.confirm.setProperty("primary", True)

        self.confirm.clicked.connect(
            self._accept_item
        )

        actions.addWidget(cancel)
        actions.addWidget(self.confirm)

        layout.addLayout(actions)

        self._refresh()

    def _stepper(self, label, action):
        row = QHBoxLayout()

        minus = QPushButton("−")
        minus.setFixedSize(64, 56)

        minus.clicked.connect(
            lambda _=False: action(-1)
        )

        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        label.setMinimumWidth(54)

        plus = QPushButton("+")
        plus.setFixedSize(64, 56)

        plus.clicked.connect(
            lambda _=False: action(1)
        )

        row.addWidget(minus)
        row.addWidget(label)
        row.addWidget(plus)

        return row

    def _option(self, value):
        self.option = value
        self._refresh()

    def _volume(self, amount):
        self.quantity = amount

        self.count_label.setText(
            format_quantity(amount) + " L"
        )

        self.volume_group.setExclusive(False)

        for button in self.volume_group.buttons():
            button.setChecked(
                button.text()
                == format_quantity(amount) + " L"
            )

        self.volume_group.setExclusive(True)

        self._refresh()

    def _custom_volume(self):
        amount = VolumeDialog.choose(
            self.quantity,
            self,
        )

        if amount is not None:
            self._volume(amount)

    def _count(self, delta):
        self.quantity = max(
            Decimal(1),
            self.quantity + delta,
        )

        self.count_label.setText(
            format_quantity(self.quantity)
        )

        self._refresh()

    def _product_price(self):
        if not self.is_jizz:
            return

        value = NumberDialog.money(
            self,
            self.product["name"],
            self.product.get(
                "manual_price_presets", []
            ),
            self.manual_price or 0,
        )

        if value is None:
            return

        if value <= 0:
            QMessageBox.warning(
                self,
                "Jizz",
                "Narx 0 dan katta bo‘lishi kerak.",
            )
            return

        self.manual_price = value
        self._refresh()

    def _set_product_price(self, amount):
        if not self.is_jizz:
            return

        if amount <= 0:
            return

        self.manual_price = amount
        self._refresh()

    def _manual_addon(self, addon):
        if not _is_gosht(addon.get("name", "")):
            return

        existing = self.addons.get(addon["id"])

        value = NumberDialog.money(
            self,
            addon["name"],
            addon.get(
                "manual_price_presets", []
            ),
            existing.manual_price
            if existing
            else 0,
        )

        if value is not None:
            self._set_manual_addon(
                addon,
                value,
            )

    def _set_manual_addon(self, addon, value):
        if not _is_gosht(addon.get("name", "")):
            return

        if value < 5000:
            QMessageBox.warning(
                self,
                "Go‘sht",
                "Eng kam summa: 5 000 so‘m",
            )
            return

        self.addons[addon["id"]] = CartAddOn(
            addon["id"],
            addon["name"],
            Decimal(1),
            value,
            value,
        )

        self.addon_labels[
            addon["id"]
        ].setText(format_money(value))

        self._refresh()

    def _remove_addon(self, addon):
        if not addon.get("is_required"):
            self.addons.pop(
                addon["id"],
                None,
            )

            self.addon_labels[
                addon["id"]
            ].setText("—")

            self._refresh()

    def _addon_count(self, addon, delta):
        if _is_gosht(addon.get("name", "")):
            return

        if addon.get("base_price", 0) <= 0:
            QMessageBox.warning(
                self,
                "Narx",
                "Narx sozlanmagan. "
                "Administratorga murojaat qiling.",
            )
            return

        current = self.addons.get(addon["id"])

        minimum = Decimal(
            1 if addon.get("is_required") else 0
        )

        quantity = max(
            minimum,
            (
                current.quantity
                if current
                else Decimal(0)
            )
            + delta,
        )

        if quantity:
            self.addons[addon["id"]] = CartAddOn(
                addon["id"],
                addon["name"],
                quantity,
                addon["base_price"],
            )

        else:
            self.addons.pop(
                addon["id"],
                None,
            )

        self.addon_labels[
            addon["id"]
        ].setText(
            format_quantity(quantity)
        )

        self._refresh()

    def _item(self):
        if self.is_osh and self.option is None:
            raise CartValidationError(
                "Osh porsiyasini tanlang; "
                "narx sozlanmagan bo‘lsa "
                "Administratorga murojaat qiling"
            )

        if (
            any(
                option.get("is_active", True)
                for option in self.product.get(
                    "price_options", []
                )
            )
            and self.option is None
        ):
            raise CartValidationError(
                "Variantni tanlang"
            )

        if self.is_jizz and (
            self.manual_price is None
            or self.manual_price <= 0
        ):
            raise CartValidationError(
                "Jizz narxini tanlang yoki kiriting"
            )

        for addon in _unique_available_addons(
            self.product
        ):
            if (
                addon.get("is_required")
                and addon["id"] not in self.addons
            ):
                raise CartValidationError(
                    f"{addon['name']}ni tanlang"
                )

        item = CartItem.from_catalog(
            self.product,
            self.quantity,
            self.option,
            self.manual_price,
            tuple(self.addons.values()),
        )

        _ = item.total_price

        return item

    def _refresh(self):
        try:
            item = self._item()

        except CartValidationError as error:
            self.total.setText(str(error))
            self.confirm.setEnabled(False)

        else:
            self.total.setText(
                f"Jami: "
                f"{format_money(item.total_price)}"
            )

            self.confirm.setEnabled(True)

    def _accept_item(self):
        self.result_item = self._item()
        self.accept()

    @classmethod
    def choose(
        cls,
        product,
        existing=None,
        parent=None,
    ):
        dialog = cls(
            product,
            existing,
            parent,
        )

        return (
            dialog.result_item
            if dialog.exec()
            == QDialog.DialogCode.Accepted
            else None
        )
