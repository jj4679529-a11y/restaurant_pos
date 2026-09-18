"""Restaurant-facing reusable admin forms.

Drafts never write until Save. Product images are staged before the record is saved.
The UI enforces the final restaurant pricing rules so cashiers cannot accidentally
receive editable prices for ordinary products.
"""
from pathlib import Path

from PySide6.QtCore import Qt

from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QScroller,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.menu_rules import PIECE_DRINKS
from app.ui.admin.api import menu_name
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.widgets.product_card import product_pixmap


UNITS = [
    ("Porsiya", "PORTION"),
    ("Dona", "PIECE"),
    ("Litr", "LITER"),
    ("Qo‘lda narx", "AMOUNT"),
]


def _key(value):
    """Normalize an owner-facing Uzbek name for simple UI classification."""
    text = menu_name(value or "")
    return (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("ʻ", "'")
        .strip()
    )


def _is_osh_name(value):
    key = _key(value)
    return key == "osh" or key.endswith(" osh")


def _is_gosht(value):
    return _key(value) in {"gosht", "go'sht"}


def _is_jizz(value):
    return _key(value) == "jizz"


def _is_qazi(value):
    return _key(value) == "qazi"


def _is_tuxum(value):
    key = _key(value)
    return key.startswith("tuxum") or key.startswith("bedana tuxum")


def _is_manti(value):
    return _key(value) == "manti"


def _is_portion_food(value):
    key = _key(value)
    return (
        _is_osh_name(value)
        or key in {
            "shorva",
            "sho'rva",
            "koza shorva",
            "ko'za shorva",
            "mastava",
        }
    )


class Editor(QDialog):
    def __init__(self, title, fields, values, save, on_error, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 680)

        self.save_callback = save
        self.on_error = on_error
        self.widgets = {}
        self.field_rows = {}
        self.saved = False

        layout = QVBoxLayout(self)

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
        content.setObjectName("adminFormPanel")
        self.form = QFormLayout(content)
        self.form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        self.form.setSpacing(18)
        self.form.setContentsMargins(18, 18, 18, 18)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        for key, label, kind in fields:
            self.field_rows[key] = self.form.rowCount()
            value = values.get(key)

            if isinstance(kind, list):
                widget = QComboBox()
                widget.setMinimumHeight(52)
                for name, data in kind:
                    widget.addItem(name, data)
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)

            elif kind == "bool":
                widget = QCheckBox("Sotuvda")
                widget.setChecked(bool(value if value is not None else True))
                widget.setMinimumHeight(52)

            elif kind in {"money", "int"}:
                widget = QSpinBox()
                widget.setRange(
                    0 if kind == "money" else -2_147_483_647,
                    2_147_483_647,
                )
                widget.setValue(int(value or 0))
                widget.setMinimumHeight(52)
                if kind == "money":
                    widget.setSuffix(" so‘m")

            else:
                widget = QLineEdit(str(value or ""))
                widget.setMinimumHeight(52)
                if kind == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
                    widget.setPlaceholderText(
                        "Faqat yangi parol; bo‘sh bo‘lsa o‘zgarmaydi"
                    )
                if kind == "readonly":
                    widget.setReadOnly(True)

            widget.setObjectName(key)
            self.widgets[key] = widget

            if kind == "money":
                row = QHBoxLayout()
                row.addWidget(widget, 1)

                keypad = QPushButton("NARXNI KIRITISH")
                keypad.setMinimumHeight(52)
                keypad.clicked.connect(
                    lambda _=False, field=widget: self.money_keypad(field)
                )
                row.addWidget(keypad)
                self.form.addRow(label, row)
            else:
                self.form.addRow(label, widget)

        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)

        buttons = QHBoxLayout()

        cancel = QPushButton("BEKOR QILISH")
        cancel.setMinimumHeight(58)
        cancel.clicked.connect(self.reject)

        self.save_button = QPushButton("✓ SAQLASH")
        self.save_button.setProperty("primary", True)
        self.save_button.setMinimumHeight(58)
        self.save_button.clicked.connect(self.save)

        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)

        self.initial = self.values()

    def money_keypad(self, field):
        if not field.isEnabled():
            return

        amount = NumberDialog.money(
            self,
            "Narx",
            initial=field.value(),
        )

        if amount is not None:
            field.setValue(amount)

    def values(self):
        result = {}

        for key, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                result[key] = widget.currentData()
            elif isinstance(widget, QCheckBox):
                result[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                result[key] = widget.value()
            else:
                result[key] = (
                    widget.text()
                    if key == "password"
                    else widget.text().strip()
                )

        return result

    def discard(self):
        if self.saved or self.values() == self.initial:
            return True

        return (
            QMessageBox.question(
                self,
                "Saqlanmagan o‘zgarishlar",
                "O‘zgarishlarni saqlamasdan chiqasizmi?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def reject(self):
        if self.discard():
            if "password" in self.widgets:
                self.widgets["password"].clear()
            super().reject()

    def closeEvent(self, event):
        if self.discard():
            if "password" in self.widgets:
                self.widgets["password"].clear()
            event.accept()
        else:
            event.ignore()

    def save(self):
        data = self.values()

        if (
            self.initial.get("is_active")
            and data.get("is_active") is False
        ):
            answer = QMessageBox.question(
                self,
                "Tasdiqlash",
                "Yozuvni nofaol qilasizmi?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.save_button.setEnabled(False)

        try:
            self.save_callback(data)
        except Exception as error:
            self.on_error(error)
        else:
            self.saved = True
            if "password" in self.widgets:
                self.widgets["password"].clear()
            self.accept()
        finally:
            self.save_button.setEnabled(True)


def fields_for(resource, client, original):
    active = [("is_active", "Sotuvda faol", "bool")]
    named = [("name", "Mahsulot nomi", "text")]

    if resource == "categories":
        return named + [("sort_order", "Tartibi", "int")] + active

    if resource in {"products", "addons"}:
        fields = (
            named
            + [
                ("unit_type", "Sotish usuli", UNITS),
                ("base_price", "Sotuv narxi", "money"),
                (
                    "allows_manual_price",
                    "Kassir boshqa narx kirita oladi",
                    "bool",
                ),
            ]
            + active
        )

        if resource == "products":
            categories = [
                (category["name"], category["id"])
                for category in client.list_records("categories")
            ]
            fields.insert(
                1,
                ("category_id", "Menyu bo‘limi", categories),
            )
            fields.append(
                ("image_path", "Mahsulot rasmi", "readonly")
            )
            fields.append(
                (
                    "volume_liters",
                    "Hajmi (masalan 0.5 L / 1 L)",
                    "text",
                )
            )

        return fields

    if resource == "workers":
        return named + [("phone", "Telefon raqami", "text")] + active

    if resource == "users":
        return (
            named
            + [
                ("phone", "Telefon raqami", "text"),
                ("username", "Kirish logini", "text"),
                (
                    "role",
                    "Rol",
                    [
                        ("Kassir", "CASHIER"),
                        ("Administrator", "ADMIN"),
                    ],
                ),
                ("password", "Yangi parol", "password"),
            ]
            + active
        )

    if resource == "printers":
        return (
            named
            + [
                ("terminal_name", "Qaysi kassa / terminal", "text"),
                (
                    "connection_type",
                    "Ulanish",
                    [
                        ("USB", "USB"),
                        ("Tarmoq", "NETWORK"),
                    ],
                ),
                ("address", "Printer manzili / qurilma nomi", "text"),
            ]
            + active
        )

    if resource == "presets":
        targets = []

        for group in ("products", "addons"):
            for row in client.list_records(group):
                target_field = (
                    "product_id"
                    if group == "products"
                    else "addon_id"
                )

                if (
                    row.get("allows_manual_price")
                    or (
                        original
                        and original.get(target_field) == row["id"]
                    )
                ):
                    targets.append(
                        (
                            f"{row['name']} · "
                            f"{'Mahsulot' if group == 'products' else 'Qo‘shimcha'}",
                            f"{target_field}:{row['id']}",
                        )
                    )

        return [
            (
                "target",
                "Tegishli mahsulot / qo‘shimcha",
                targets,
            ),
            ("amount", "Summa", "money"),
            ("sort_order", "Tartibi", "int"),
        ] + active

    if resource == "settings":
        key = original["key"]
        labels = {
            "timezone": "Vaqt mintaqasi",
            "business_day_start": "Ish kuni boshlanishi (HH:MM)",
            "restaurant_name": "Restoran nomi",
        }
        return [
            ("value", labels.get(key, key), "text")
        ]

    raise ValueError(resource)


class RecordEditor(Editor):
    def __init__(
        self,
        resource,
        client,
        original,
        on_error,
        parent=None,
    ):
        self.resource = resource
        self.client = client
        self.original = original

        values = dict(original or {})
        values.setdefault("allows_manual_price", False)

        if resource == "presets" and original:
            field = (
                "product_id"
                if original.get("product_id")
                else "addon_id"
            )
            values["target"] = f"{field}:{original[field]}"

        fields = fields_for(
            resource,
            client,
            original,
        )

        titles = {
            "products": (
                "Mahsulotni tahrirlash"
                if original
                else "Yangi mahsulot"
            ),
            "addons": (
                "Qo‘shimchani tahrirlash"
                if original
                else "Yangi qo‘shimcha"
            ),
            "workers": (
                "Yetkazib beruvchini tahrirlash"
                if original
                else "Yangi yetkazib beruvchi"
            ),
            "users": (
                "Kassirni tahrirlash"
                if original
                else "Yangi kassir"
            ),
            "printers": (
                "Printerni tahrirlash"
                if original
                else "Yangi printer"
            ),
            "categories": (
                "Menyu bo‘limini tahrirlash"
                if original
                else "Yangi menyu bo‘limi"
            ),
        }

        super().__init__(
            titles.get(
                resource,
                "Tahrirlash" if original else "Yangi yozuv",
            ),
            fields,
            values,
            self.persist,
            on_error,
            parent,
        )

        self.category_names = {}

        if resource == "products":
            try:
                self.category_names = {
                    category["id"]: _key(category["name"])
                    for category in client.list_records("categories")
                }
            except Exception:
                self.category_names = {}

            self.form.setRowVisible(
                self.field_rows["image_path"],
                False,
            )

            self.preview = QLabel()
            self.form.addRow(self.preview)
            self.image_preview()

            actions = QHBoxLayout()

            for label, handler in [
                (
                    "RASM TANLASH / ALMASHTIRISH",
                    self.choose_image,
                ),
                (
                    "RASMNI O‘CHIRISH",
                    self.remove_image,
                ),
            ]:
                button = QPushButton(label)
                button.setMinimumHeight(52)
                button.clicked.connect(handler)
                actions.addWidget(button)

            self.form.addRow(actions)

        if resource in {"products", "addons"}:
            self._connect_product_rules()
            self.apply_menu_rules()

        if resource == "presets" and original:
            self.widgets["target"].setEnabled(False)

        self.initial = self.values()

    def _connect_product_rules(self):
        if "name" in self.widgets:
            self.widgets["name"].textChanged.connect(
                lambda _text: self.apply_menu_rules()
            )

        if (
            self.resource == "products"
            and "category_id" in self.widgets
        ):
            self.widgets[
                "category_id"
            ].currentIndexChanged.connect(
                lambda _index: self.apply_menu_rules()
            )

        if "unit_type" in self.widgets:
            self.widgets[
                "unit_type"
            ].currentIndexChanged.connect(
                lambda _index: self._update_price_label()
            )

    def _category_key(self):
        if (
            self.resource != "products"
            or "category_id" not in self.widgets
        ):
            return ""

        return self.category_names.get(
            self.widgets["category_id"].currentData(),
            "",
        )

    def _is_piece_category(self):
        category = self._category_key()

        return category in {
            "salatlar",
            "nonlar",
            "choy va novot",
            "kompot va ayron",
            "salqin ichimliklar",
        }

    def _is_cold_drink_category(self):
        return self._category_key() == "salqin ichimliklar"

    def _is_compot_ayron_category(self):
        return self._category_key() == "kompot va ayron"

    def _set_unit(self, value):
        widget = self.widgets.get("unit_type")
        if not widget:
            return

        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)

    def _set_manual(self, enabled):
        widget = self.widgets.get("allows_manual_price")
        if widget:
            widget.setChecked(enabled)

    def _set_row_visible(self, key, visible):
        if key in self.field_rows:
            self.form.setRowVisible(
                self.field_rows[key],
                visible,
            )

    def _set_field_label(self, key, text):
        widget = self.widgets.get(key)
        if not widget:
            return

        label = self.form.labelForField(widget)

        if label:
            label.setText(text)

    def apply_menu_rules(self):
        if self.resource not in {"products", "addons"}:
            return

        name = self.widgets.get("name")
        name = name.text() if name else ""
        key = _key(name)

        unit_widget = self.widgets.get("unit_type")
        manual_widget = self.widgets.get(
            "allows_manual_price"
        )
        price_widget = self.widgets.get("base_price")

        # Safe default: ordinary items never allow cashier-entered prices.
        if manual_widget:
            manual_widget.setChecked(False)
            manual_widget.setEnabled(False)

        if unit_widget:
            unit_widget.setEnabled(False)

        self._set_row_visible("unit_type", False)
        self._set_row_visible(
            "allows_manual_price",
            False,
        )
        self._set_row_visible("base_price", True)

        if self.resource == "products":
            self._set_row_visible(
                "volume_liters",
                False,
            )

        self._set_field_label(
            "base_price",
            "Sotuv narxi",
        )

        # Go‘sht is an Osh-only addon, never a standalone product.
        if _is_gosht(name):
            self._set_unit("AMOUNT")
            self._set_manual(True)
            if price_widget:
                price_widget.setValue(0)
                price_widget.setEnabled(False)
            self._set_row_visible("base_price", False)
            self._update_price_label()
            return

        # Jizz is the only standalone manually-priced product.
        if _is_jizz(name):
            self._set_unit("AMOUNT")
            self._set_manual(True)
            if price_widget:
                price_widget.setValue(0)
                price_widget.setEnabled(False)
            self._set_row_visible("base_price", False)
            self._update_price_label()
            return

        # Osh keeps its configured portion options outside base_price.
        if _is_osh_name(name):
            self._set_unit("PORTION")
            if price_widget:
                price_widget.setValue(0)
                price_widget.setEnabled(False)
            self._set_row_visible("base_price", False)
            self._update_price_label()
            return

        # Tuxum / Bedana tuxum / Qazi are always price-per-piece.
        if (
            _is_tuxum(name)
            or _is_qazi(name)
            or _is_manti(name)
            or self._is_piece_category()
            or key in PIECE_DRINKS
            or key in {"choy", "novot"}
        ):
            self._set_unit("PIECE")

            if price_widget:
                price_widget.setEnabled(True)

            self._set_field_label(
                "base_price",
                "Dona narxi",
            )

            self._update_price_label()

            # Only cold drinks show package-size metadata.
            if self.resource == "products":
                self._set_row_visible(
                    "volume_liters",
                    self._is_cold_drink_category(),
                )

                if self._is_cold_drink_category():
                    self._set_field_label(
                        "volume_liters",
                        "Hajmi (masalan 0.5 L / 1 L / 1.5 L)",
                    )

            return

        # Sho‘rva / Ko‘za sho‘rva / Mastava are configured portion-price items.
        if _is_portion_food(name):
            self._set_unit("PORTION")

            if price_widget:
                price_widget.setEnabled(True)

            self._set_field_label(
                "base_price",
                "Porsiya narxi",
            )

            self._update_price_label()
            if self.resource == "products":
                self._set_row_visible("volume_liters", False)
            return

        # Unknown/general products: owner may choose only
        # understandable Dona / Porsiya options.
        if unit_widget:
            current = unit_widget.currentData()

            unit_widget.blockSignals(True)
            unit_widget.clear()
            unit_widget.addItem("Dona", "PIECE")
            unit_widget.addItem("Porsiya", "PORTION")

            index = unit_widget.findData(
                current if current in {"PIECE", "PORTION"} else "PIECE"
            )
            unit_widget.setCurrentIndex(
                index if index >= 0 else 0
            )
            unit_widget.blockSignals(False)
            unit_widget.setEnabled(True)

        self._set_field_label(
            "unit_type",
            "Sotish usuli",
        )
        self._set_row_visible("unit_type", True)
        self._set_row_visible(
            "allows_manual_price",
            False,
        )

        if price_widget:
            price_widget.setEnabled(True)

        if self.resource == "products":
            self._set_row_visible(
                "volume_liters",
                self._is_cold_drink_category(),
            )

        self._update_price_label()

    def _update_price_label(self):
        if "base_price" not in self.field_rows:
            return

        label_item = self.form.itemAt(
            self.field_rows["base_price"],
            QFormLayout.ItemRole.LabelRole,
        )

        if not label_item or not label_item.widget():
            return

        unit = (
            self.widgets["unit_type"].currentData()
            if "unit_type" in self.widgets
            else None
        )

        if unit == "PIECE":
            text = "Dona narxi"
        elif unit == "PORTION":
            text = "Porsiya narxi"
        else:
            text = "Narxi"

        label_item.widget().setText(text)

    def image_preview(self):
        reference = self.widgets["image_path"].text()
        self.preview.setPixmap(
            product_pixmap(
                self.client.load_image(reference)
            )
        )

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Mahsulot rasmi",
            "",
            "Rasmlar (*.png *.jpg *.jpeg *.webp)",
        )

        if not path:
            return

        try:
            if Path(path).stat().st_size > 5 * 1024 * 1024:
                raise ValueError(
                    "Rasm hajmi 5 MB dan oshmasin"
                )

            data = Path(path).read_bytes()

            if QImage.fromData(data).isNull():
                raise ValueError(
                    "Rasm formati noto‘g‘ri"
                )

            reference = self.client.upload_image(data)
            self.widgets["image_path"].setText(reference)
            self.image_preview()

        except Exception as error:
            self.on_error(error)

    def remove_image(self):
        self.widgets["image_path"].clear()
        self.image_preview()

    def persist(self, data):
        if (
            self.resource
            in {
                "categories",
                "products",
                "addons",
                "workers",
                "users",
                "printers",
            }
            and not data.get("name", "").strip()
        ):
            raise ValueError("Nomini kiriting")

        if self.resource == "products":
            name = data.get("name", "")
            category = self.category_names.get(
                data.get("category_id"),
                "",
            )

            # Go‘sht must remain Osh-only addon.
            if _is_gosht(name):
                raise ValueError(
                    "Go‘sht alohida mahsulot emas. "
                    "Uni Osh qo‘shimchasi sifatida sozlang."
                )

            data["image_path"] = (
                data["image_path"] or None
            )

            # Only cold drinks need package/liter metadata.
            if category == "salqin ichimliklar":
                volume = (
                    data.get("volume_liters", "")
                    .replace(",", ".")
                    .strip()
                )
                if not volume:
                    raise ValueError(
                        "Salqin ichimlik hajmini kiriting"
                    )
                data["volume_liters"] = volume
            else:
                data["volume_liters"] = None

            key = _key(name)

            if _is_jizz(name):
                data["unit_type"] = "AMOUNT"
                data["allows_manual_price"] = True
                data["base_price"] = 0

            elif _is_osh_name(name):
                data["unit_type"] = "PORTION"
                data["allows_manual_price"] = False
                data["base_price"] = 0

            elif (
                _is_manti(name)
                or category
                in {
                    "salatlar",
                    "nonlar",
                    "choy va novot",
                    "kompot va ayron",
                    "salqin ichimliklar",
                }
                or key in PIECE_DRINKS
                or key in {"choy", "novot"}
            ):
                data["unit_type"] = "PIECE"
                data["allows_manual_price"] = False
                if data["base_price"] <= 0:
                    raise ValueError(
                        "Dona narxini kiriting"
                    )

            elif _is_portion_food(name):
                data["unit_type"] = "PORTION"
                data["allows_manual_price"] = False
                if data["base_price"] <= 0:
                    raise ValueError(
                        "Porsiya narxini kiriting"
                    )

            else:
                # Manual cashier pricing is forbidden for all other products.
                data["allows_manual_price"] = False
                if data.get("unit_type") == "AMOUNT":
                    data["unit_type"] = "PIECE"
                if data["base_price"] <= 0:
                    raise ValueError(
                        "Narxni kiriting"
                    )

        if self.resource == "addons":
            name = data.get("name", "")

            if _is_gosht(name):
                data["unit_type"] = "AMOUNT"
                data["allows_manual_price"] = True
                data["base_price"] = 0
            else:
                # Tuxum, Bedana tuxum and Qazi (and any ordinary addon)
                # are fixed-price piece addons.
                data["unit_type"] = "PIECE"
                data["allows_manual_price"] = False
                if data["base_price"] <= 0:
                    raise ValueError(
                        "Qo‘shimcha dona narxini kiriting"
                    )

        if self.resource == "presets":
            target = data.pop("target")

            if not target:
                raise ValueError(
                    "Avval qo‘lda narxli mahsulot yoki "
                    "qo‘shimchani sozlang"
                )

            if data["amount"] <= 0:
                raise ValueError(
                    "Tezkor narx 0 dan katta bo‘lishi kerak"
                )

            if not self.original:
                field, record_id = target.split(":")
                data[field] = int(record_id)

        if (
            self.resource == "users"
            and self.original
            and not data.get("password")
        ):
            data.pop("password", None)

        self.client.save_record(
            self.resource,
            data,
            self.original,
        )
