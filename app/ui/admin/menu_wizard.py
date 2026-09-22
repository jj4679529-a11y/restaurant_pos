from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
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

from app.ui.admin.api import menu_name
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.widgets.product_card import product_pixmap


MILLIY = [
    "Osh",
    "Osh qo‘shimchalari",
    "Shurva",
    "Ko‘za shurva",
    "Jizz",
    "Mastava",
    "Manti",
]

ROOT_SECTIONS = [
    "Milliy taomlar",
    "Salatlar",
    "Choy va Novot",
    "Nonlar",
    "Kompot va Ayron",
    "Salqin ichimliklar",
]

ADDONS = [
    "Tuxum",
    "Bedana tuxum",
    "Qazi",
    "Go‘sht",
]

LITERS = [
    ("0.5 L", "0.5"),
    ("1 L", "1"),
    ("1.5 L", "1.5"),
    ("2 L", "2"),
]


OSH_PORTIONS = [
    ("0.5 porsiya", "0.5"),
    ("0.7 porsiya", "0.7"),
    ("1 porsiya", "1"),
]

BREAD = [
    ("Butun", "Butun"),
    ("Yarim", "Yarim"),
    ("Chorak", "Chorak"),
]


def _key(value):
    return menu_name(value or "")


class ChoiceDialog(QDialog):
    def __init__(self, title, choices, parent=None):
        super().__init__(parent)
        self.choice = None

        self.setWindowTitle(title)
        self.resize(700, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title_label = QLabel(title)
        title_label.setObjectName("dialogTitle")
        title_label.setStyleSheet(
            "font-size: 24px; font-weight: 800;"
        )
        root.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        QScroller.grabGesture(
            scroll.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(12)

        for index, choice in enumerate(choices):
            button = QPushButton(choice)
            button.setMinimumHeight(72)
            button.setProperty("role", "secondary")
            button.clicked.connect(
                lambda _=False, value=choice: self.select(value)
            )
            grid.addWidget(
                button,
                index // 2,
                index % 2,
            )

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        cancel = QPushButton("BEKOR QILISH")
        cancel.setMinimumHeight(56)
        cancel.clicked.connect(self.reject)
        root.addWidget(cancel)

    def select(self, value):
        self.choice = value
        self.accept()


class StrictCreateDialog(QDialog):
    def __init__(
        self,
        client,
        selection,
        category,
        on_error,
        parent=None,
    ):
        super().__init__(parent)

        self.client = client
        self.selection = selection
        self.category = category
        self.on_error = on_error

        self.image_path = None
        self.saved = False

        self.setWindowTitle("Yangi mahsulot")
        self.resize(760, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel(selection)
        title.setObjectName("dialogTitle")
        title.setStyleSheet(
            "font-size: 24px; font-weight: 800;"
        )
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        QScroller.grabGesture(
            scroll.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        content = QWidget()
        self.form = QFormLayout(content)
        self.form.setSpacing(18)
        self.form.setContentsMargins(16, 16, 16, 16)

        self.name = QLineEdit()
        self.name.setMinimumHeight(54)

        self.price = QSpinBox()
        self.price.setRange(0, 2_147_483_647)
        self.price.setSuffix(" so‘m")
        self.price.setMinimumHeight(54)

        # Osh: admin sotiladigan porsiyalarni o'zi tanlaydi.
        self.osh_prices = {}
        for label, _value in OSH_PORTIONS:
            field = QSpinBox()
            field.setRange(0, 2_147_483_647)
            field.setSuffix(" so‘m")
            field.setMinimumHeight(54)
            self.osh_prices[label] = field

        self.price_button = QPushButton("NARXNI KIRITISH")
        self.price_button.setMinimumHeight(54)
        self.price_button.clicked.connect(
            lambda: self.money(self.price)
        )

        self.price_row = QHBoxLayout()
        self.price_row.addWidget(self.price, 1)
        self.price_row.addWidget(self.price_button)

        self.volume = QComboBox()
        self.volume.setMinimumHeight(54)
        for label, value in LITERS:
            self.volume.addItem(label, value)

        self.bread = QComboBox()
        self.bread.setMinimumHeight(54)
        for label, value in BREAD:
            self.bread.addItem(label, value)

        self.preview = QLabel("Rasm tanlanmagan")
        self.preview.setMinimumHeight(100)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        image_row = QHBoxLayout()

        choose = QPushButton("RASM TANLASH")
        choose.setMinimumHeight(54)
        choose.clicked.connect(self.choose_image)

        remove = QPushButton("RASMNI O‘CHIRISH")
        remove.setMinimumHeight(54)
        remove.clicked.connect(self.remove_image)

        image_row.addWidget(choose)
        image_row.addWidget(remove)

        self.presets = []

        self.bread_prices = {}
        for label, _value in BREAD:
            field = QSpinBox()
            field.setRange(0, 2_147_483_647)
            field.setSuffix(" so‘m")
            field.setMinimumHeight(54)
            self.bread_prices[label] = field

        self.liter_prices = {}
        for label, _value in LITERS:
            field = QSpinBox()
            field.setRange(0, 2_147_483_647)
            field.setSuffix(" so‘m")
            field.setMinimumHeight(54)
            self.liter_prices[label] = field

        self.build_form()

        self.form.addRow("Rasm (ixtiyoriy)", self.preview)
        self.form.addRow(image_row)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        actions = QHBoxLayout()

        cancel = QPushButton("BEKOR QILISH")
        cancel.setMinimumHeight(58)
        cancel.clicked.connect(self.reject)

        save = QPushButton("✓ SAQLASH")
        save.setProperty("primary", True)
        save.setMinimumHeight(58)
        save.clicked.connect(self.save)

        actions.addWidget(cancel)
        actions.addWidget(save)

        root.addLayout(actions)

    def fixed_value(self, text):
        label = QLabel(text)
        label.setMinimumHeight(54)
        label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )
        return label

    def add_price(self, label="Narxi"):
        self.form.addRow(label, self.price_row)

    def build_form(self):
        s = self.selection

        if s == "Osh":
            self.form.addRow(
                "Mahsulot nomi",
                self.name,
            )

            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Porsiyada"),
            )

            for label, _value in OSH_PORTIONS:
                field = self.osh_prices[label]

                row = QHBoxLayout()
                row.addWidget(field, 1)

                button = QPushButton("NARX")
                button.setMinimumHeight(54)
                button.clicked.connect(
                    lambda _=False, f=field: self.money(f)
                )

                row.addWidget(button)
                self.form.addRow(
                    f"{label} narxi",
                    row,
                )

            return

        if s in {"Shurva", "Ko‘za shurva", "Mastava"}:
            self.form.addRow(
                "Mahsulot nomi",
                self.name,
            )
            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Porsiyada"),
            )
            self.add_price("Narxi")
            return

        if s == "Manti":
            self.form.addRow(
                "Mahsulot nomi",
                self.name,
            )
            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Donada"),
            )
            self.add_price("Narxi")
            return

        if s in {"Salatlar", "Choy va Novot"}:
            self.form.addRow(
                "Mahsulot nomi",
                self.name,
            )
            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Donada"),
            )
            self.add_price("Narxi")
            return

        if s == "Nonlar":
            self.form.addRow(
                "Mahsulot nomi",
                self.name,
            )
            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Variantlar bo‘yicha"),
            )

            for label, _value in BREAD:
                field = self.bread_prices[label]

                row = QHBoxLayout()
                row.addWidget(field, 1)

                button = QPushButton("NARX")
                button.setMinimumHeight(54)
                button.clicked.connect(
                    lambda _=False, f=field: self.money(f)
                )

                row.addWidget(button)
                self.form.addRow(f"{label} narxi", row)

            return

        if s in {
            "Kompot va Ayron",
            "Salqin ichimliklar",
        }:
            self.form.addRow(
                "Mahsulot nomi",
                self.name,
            )
            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Litrda"),
            )

            for label, _value in LITERS:
                field = self.liter_prices[label]

                row = QHBoxLayout()
                row.addWidget(field, 1)

                button = QPushButton("NARX")
                button.setMinimumHeight(54)
                button.clicked.connect(
                    lambda _=False, f=field: self.money(f)
                )

                row.addWidget(button)
                self.form.addRow(f"{label} narxi", row)

            return

        if s in {"Tuxum", "Bedana tuxum", "Qazi"}:
            self.name.setText(s)
            self.name.setReadOnly(True)

            self.form.addRow(
                "Qo‘shimcha",
                self.name,
            )
            self.form.addRow(
                "Sotish usuli",
                self.fixed_value("Donada"),
            )
            self.add_price("Narxi")
            return

        if s in {"Go‘sht", "Jizz"}:
            self.name.setText(s)

            if s == "Go‘sht":
                self.name.setReadOnly(True)

            self.form.addRow(
                "Mahsulot nomi"
                if s == "Jizz"
                else "Qo‘shimcha",
                self.name,
            )

            self.form.addRow(
                "Sotish usuli",
                self.fixed_value(
                    "Kassir qo‘lda narx kiritadi"
                ),
            )

            for index in range(4):
                field = QSpinBox()
                field.setRange(0, 2_147_483_647)
                field.setSuffix(" so‘m")
                field.setMinimumHeight(54)

                row = QHBoxLayout()
                row.addWidget(field, 1)

                button = QPushButton("NARX")
                button.setMinimumHeight(54)
                button.clicked.connect(
                    lambda _=False, f=field:
                    self.money(f)
                )

                row.addWidget(button)

                self.form.addRow(
                    f"Tezkor narx {index + 1}",
                    row,
                )

                self.presets.append(field)

    def money(self, field):
        amount = NumberDialog.money(
            self,
            "Narx",
            initial=field.value(),
        )

        if amount is not None:
            field.setValue(amount)

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
            file = Path(path)

            if file.stat().st_size > 5 * 1024 * 1024:
                raise ValueError(
                    "Rasm hajmi 5 MB dan oshmasin"
                )

            data = file.read_bytes()

            if QImage.fromData(data).isNull():
                raise ValueError(
                    "Rasm formati noto‘g‘ri"
                )

            self.image_path = self.client.upload_image(data)

            self.preview.setPixmap(
                product_pixmap(
                    self.client.load_image(
                        self.image_path
                    )
                )
            )

        except Exception as error:
            self.on_error(error)

    def remove_image(self):
        self.image_path = None
        self.preview.clear()
        self.preview.setText("Rasm tanlanmagan")

    def _save_presets(self, target, resource):
        values = [
            field.value()
            for field in self.presets
            if field.value() > 0
        ]

        if len(values) != len(set(values)):
            raise ValueError(
                "Tezkor narxlar bir xil bo‘lmasin"
            )

        if self.selection == "Go‘sht":
            if any(value < 5000 for value in values):
                raise ValueError(
                    "Go‘sht tezkor narxi kamida "
                    "5 000 so‘m bo‘lishi kerak"
                )

        target_field = (
            "product_id"
            if resource == "products"
            else "addon_id"
        )

        for index, amount in enumerate(values):
            self.client.request(
                "POST",
                "/api/manual-price-presets",
                {
                    target_field: target["id"],
                    "amount": amount,
                    "sort_order": index,
                    "is_active": True,
                },
            )

    def _find_osh(self):
        products = self.client.list_records("products")

        return next(
            (
                product
                for product in products
                if _key(product.get("name")) == "osh"
                and product.get("is_active", True)
            ),
            None,
        )

    def save(self):
        try:
            name = self.name.text().strip()

            if not name:
                raise ValueError(
                    "Mahsulot nomini kiriting"
                )

            s = self.selection

            # ------------------------------------------
            # OSH ADDONS
            # ------------------------------------------
            if s in {
                "Tuxum",
                "Bedana tuxum",
                "Qazi",
                "Go‘sht",
            }:
                manual = s == "Go‘sht"

                if not manual and self.price.value() <= 0:
                    raise ValueError(
                        "Narxni kiriting"
                    )

                addon = self.client.save_record(
                    "addons",
                    {
                        "name": name,
                        "image_path": self.image_path,
                        "unit_type": (
                            "AMOUNT"
                            if manual
                            else "PIECE"
                        ),
                        "base_price": (
                            0
                            if manual
                            else self.price.value()
                        ),
                        "allows_manual_price": manual,
                        "is_active": True,
                    },
                )

                osh = self._find_osh()

                if osh:
                    self.client.set_link(
                        osh["id"],
                        addon["id"],
                        True,
                        False,
                    )

                if manual:
                    self._save_presets(
                        addon,
                        "addons",
                    )

                self.saved = True
                self.accept()
                return

            # ------------------------------------------
            # PRODUCT
            # ------------------------------------------
            if s == "Osh":
                if all(
                    field.value() <= 0
                    for field in self.osh_prices.values()
                ):
                    raise ValueError(
                        "Kamida bitta Osh porsiyasi narxini kiriting"
                    )

            elif s == "Nonlar":
                if any(
                    field.value() <= 0
                    for field in self.bread_prices.values()
                ):
                    raise ValueError(
                        "Butun, Yarim va Chorak narxlarini kiriting"
                    )

            elif s in {
                "Kompot va Ayron",
                "Salqin ichimliklar",
            }:
                if any(
                    field.value() <= 0
                    for field in self.liter_prices.values()
                ):
                    raise ValueError(
                        "0.5, 1, 1.5 va 2 litr narxlarini kiriting"
                    )

            elif (
                s != "Jizz"
                and self.price.value() <= 0
            ):
                raise ValueError(
                    "Narxni kiriting"
                )

            if s == "Jizz":
                unit = "AMOUNT"
                manual = True
                base_price = 0
                volume = None

            elif s == "Osh":
                unit = "PORTION"
                manual = False
                base_price = 0
                volume = None

            elif s in {
                "Shurva",
                "Ko‘za shurva",
                "Mastava",
            }:
                unit = "PORTION"
                manual = False
                base_price = self.price.value()
                volume = None

            elif s in {
                "Manti",
                "Salatlar",
                "Choy va Novot",
            }:
                unit = "PIECE"
                manual = False
                base_price = self.price.value()
                volume = None

            elif s == "Nonlar":
                unit = "PIECE"
                manual = False
                base_price = 0
                volume = None

            elif s in {
                "Kompot va Ayron",
                "Salqin ichimliklar",
            }:
                unit = "LITER"
                manual = False
                base_price = 0
                volume = None

            else:
                raise ValueError(
                    "Mahsulot turi aniqlanmadi"
                )

            data = {
                "category_id": self.category["id"],
                "name": name,
                "image_path": self.image_path,
                "volume_liters": volume,
                "unit_type": unit,
                "base_price": base_price,
                "allows_manual_price": manual,
                "is_active": True,
            }

            # Yangi qat’iy wizard eski protect_menu()
            # qoidalaridan mustaqil ishlaydi.
            product = self.client.request(
                "POST",
                "/api/products",
                data,
            )

            if s == "Osh":
                self.client.save_price_options(
                    product["id"],
                    [
                        {
                            "name": label,
                            "quantity": value,
                            "price": self.osh_prices[label].value(),
                        }
                        for label, value in OSH_PORTIONS
                        if self.osh_prices[label].value() > 0
                    ],
                )

            if s == "Nonlar":
                quantities = {
                    "Butun": "1",
                    "Yarim": "0.5",
                    "Chorak": "0.25",
                }

                self.client.save_price_options(
                    product["id"],
                    [
                        {
                            "name": label,
                            "quantity": quantities[label],
                            "price": self.bread_prices[label].value(),
                        }
                        for label, _value in BREAD
                    ],
                )

            if s in {
                "Kompot va Ayron",
                "Salqin ichimliklar",
            }:
                self.client.save_price_options(
                    product["id"],
                    [
                        {
                            "name": label,
                            "quantity": value,
                            "price": self.liter_prices[label].value(),
                        }
                        for label, value in LITERS
                    ],
                )

            if s == "Jizz":
                self._save_presets(
                    product,
                    "products",
                )

            self.saved = True
            self.accept()

        except Exception as error:
            self.on_error(error)


class StrictMenuWizard:
    def __init__(
        self,
        client,
        on_error,
        parent=None,
    ):
        self.client = client
        self.on_error = on_error
        self.parent = parent

    def choose(self, title, values):
        dialog = ChoiceDialog(
            title,
            values,
            self.parent,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        return dialog.choice

    def category(self, wanted):
        aliases = {
            "Milliy taomlar": {
                "milliytaomlar",
            },
            "Salatlar": {
                "salatlar",
            },
            "Choy va Novot": {
                "choyvanovot",
                "choynovot",
            },
            "Nonlar": {
                "nonlar",
            },
            "Kompot va Ayron": {
                "kompotvaayron",
            },
            "Salqin ichimliklar": {
                "salqinichimliklar",
            },
        }

        expected = aliases[wanted]

        categories = self.client.list_records(
            "categories"
        )

        return next(
            (
                category
                for category in categories
                if _key(category.get("name"))
                in expected
            ),
            None,
        )

    def run(self):
        try:
            section = self.choose(
                "Menyu bo‘limini tanlang",
                ROOT_SECTIONS,
            )

            if not section:
                return False

            category_section = section

            if section == "Milliy taomlar":
                selection = self.choose(
                    "Milliy taomlar",
                    MILLIY,
                )

                if not selection:
                    return False

                if selection == "Osh qo‘shimchalari":
                    selection = self.choose(
                        "Osh qo‘shimchalari",
                        ADDONS,
                    )

                    if not selection:
                        return False
            else:
                selection = section

            category = self.category(
                category_section
            )

            if not category:
                raise ValueError(
                    f"'{category_section}' menyu "
                    "bo‘limi topilmadi. "
                    "Avval Guruhlar bo‘limida yarating."
                )

            dialog = StrictCreateDialog(
                self.client,
                selection,
                category,
                self.on_error,
                self.parent,
            )

            return (
                dialog.exec()
                == QDialog.DialogCode.Accepted
                and dialog.saved
            )

        except Exception as error:
            self.on_error(error)
            return False


# ============================================================
# STRICT EDIT SUPPORT
# ============================================================

def _category_key(value):
    return menu_name(value or "")


def product_selection(product, categories):
    """Existing product -> strict restaurant form type."""
    category_name = ""

    for category in categories:
        if category["id"] == product.get("category_id"):
            category_name = category.get("name", "")
            break

    category = _category_key(category_name)
    name = _category_key(product.get("name", ""))

    if name == "osh":
        return "Osh"

    if name == "jizz":
        return "Jizz"

    if name == "manti":
        return "Manti"

    if name in {
        "shurva",
        "shorva",
    }:
        return "Shurva"

    if name in {
        "kozashurva",
        "kozashorva",
    }:
        return "Ko‘za shurva"

    if name == "mastava":
        return "Mastava"

    if category == "salatlar":
        return "Salatlar"

    if category in {
        "choyvanovot",
        "choynovot",
    }:
        return "Choy va Novot"

    if category == "nonlar":
        return "Nonlar"

    if category == "kompotvaayron":
        return "Kompot va Ayron"

    if category == "salqinichimliklar":
        return "Salqin ichimliklar"

    # Milliy taomlardagi boshqa mahsulotlar:
    # backend unit turiga qarab egasiga tushunarli forma.
    unit = product.get("unit_type")

    if unit == "PORTION":
        return "Shurva"

    if unit == "AMOUNT":
        return "Jizz"

    return "Manti"


class StrictEditDialog(StrictCreateDialog):
    def __init__(
        self,
        client,
        selection,
        category,
        original,
        on_error,
        parent=None,
        resource="products",
    ):
        self.original = original
        self.edit_resource = resource

        super().__init__(
            client,
            selection,
            category,
            on_error,
            parent,
        )

        self.setWindowTitle("Tahrirlash")
        self._load_original()

    def _load_original(self):
        original = self.original or {}

        self.name.setText(
            original.get("name", self.name.text())
        )

        if self.edit_resource == "addons" and self.selection in {
            "Tuxum",
            "Bedana tuxum",
            "Qazi",
            "Go‘sht",
        }:
            self.name.setReadOnly(True)

        self.image_path = original.get("image_path")

        if self.image_path:
            try:
                self.preview.setPixmap(
                    product_pixmap(
                        self.client.load_image(
                            self.image_path
                        )
                    )
                )
            except Exception:
                self.preview.setText(
                    "Rasm mavjud"
                )

        if not original.get(
            "allows_manual_price",
            False,
        ):
            self.price.setValue(
                int(original.get("base_price") or 0)
            )

        volume = original.get("volume_liters")

        if volume is not None:
            volume = str(volume).rstrip("0").rstrip(".")

            index = self.volume.findData(volume)

            if index >= 0:
                self.volume.setCurrentIndex(index)

        if self.selection == "Osh":
            for option in original.get("price_options", []):
                if not option.get("is_active", True):
                    continue

                field = self.osh_prices.get(
                    option.get("name")
                )

                if field is not None:
                    field.setValue(
                        int(option.get("price") or 0)
                    )

        if self.selection == "Nonlar":
            for option in original.get("price_options", []):
                if not option.get("is_active", True):
                    continue

                field = self.bread_prices.get(
                    option.get("name")
                )

                if field is not None:
                    field.setValue(
                        int(option.get("price") or 0)
                    )

        if self.selection in {
            "Kompot va Ayron",
            "Salqin ichimliklar",
        }:
            for option in original.get("price_options", []):
                if not option.get("is_active", True):
                    continue

                field = self.liter_prices.get(
                    option.get("name")
                )

                if field is not None:
                    field.setValue(
                        int(option.get("price") or 0)
                    )

        if self.presets:
            try:
                records = [
                    preset
                    for preset in self.client.list_records(
                        "presets"
                    )
                    if (
                        preset.get("product_id")
                        == original.get("id")
                        if self.edit_resource == "products"
                        else preset.get("addon_id")
                        == original.get("id")
                    )
                    and preset.get("is_active", True)
                ]

                records.sort(
                    key=lambda row: (
                        row.get("sort_order", 0),
                        row.get("id", 0),
                    )
                )

                for field, preset in zip(
                    self.presets,
                    records[:4],
                ):
                    field.setValue(
                        int(preset["amount"])
                    )

            except Exception as error:
                self.on_error(error)

    def _replace_presets(self):
        existing = [
            preset
            for preset in self.client.list_records(
                "presets"
            )
            if (
                preset.get("product_id")
                == self.original["id"]
                if self.edit_resource == "products"
                else preset.get("addon_id")
                == self.original["id"]
            )
        ]

        values = [
            field.value()
            for field in self.presets
            if field.value() > 0
        ]

        if len(values) != len(set(values)):
            raise ValueError(
                "Tezkor narxlar bir xil bo‘lmasin"
            )

        if self.selection == "Go‘sht":
            if any(value < 5000 for value in values):
                raise ValueError(
                    "Go‘sht tezkor narxi kamida "
                    "5 000 so‘m bo‘lishi kerak"
                )

        # Mavjud presetlarni ishlatamiz, ortiqchasini nofaol qilamiz.
        for index, amount in enumerate(values):
            data = {
                "amount": amount,
                "sort_order": index,
                "is_active": True,
            }

            if index < len(existing):
                self.client.save_record(
                    "presets",
                    data,
                    existing[index],
                )
            else:
                field = (
                    "product_id"
                    if self.edit_resource == "products"
                    else "addon_id"
                )

                data[field] = self.original["id"]

                self.client.save_record(
                    "presets",
                    data,
                )

        for preset in existing[len(values):]:
            self.client.save_record(
                "presets",
                {
                    "is_active": False,
                },
                preset,
            )

    def save(self):
        try:
            name = self.name.text().strip()

            if not name:
                raise ValueError(
                    "Mahsulot nomini kiriting"
                )

            s = self.selection

            # ----------------------------------------
            # ADDON EDIT
            # ----------------------------------------
            if self.edit_resource == "addons":
                manual = s == "Go‘sht"

                if (
                    not manual
                    and self.price.value() <= 0
                ):
                    raise ValueError(
                        "Narxni kiriting"
                    )

                self.client.save_record(
                    "addons",
                    {
                        "name": name,
                        "image_path": self.image_path,
                        "unit_type": (
                            "AMOUNT"
                            if manual
                            else "PIECE"
                        ),
                        "base_price": (
                            0
                            if manual
                            else self.price.value()
                        ),
                        "allows_manual_price": manual,
                        "is_active": self.original.get(
                            "is_active",
                            True,
                        ),
                    },
                    self.original,
                )

                if manual:
                    self._replace_presets()

                self.saved = True
                self.accept()
                return

            # ----------------------------------------
            # PRODUCT EDIT
            # ----------------------------------------
            manual = s == "Jizz"

            if s == "Osh":
                if all(
                    field.value() <= 0
                    for field in self.osh_prices.values()
                ):
                    raise ValueError(
                        "Kamida bitta Osh porsiyasi narxini kiriting"
                    )

            elif s == "Nonlar":
                if any(
                    field.value() <= 0
                    for field in self.bread_prices.values()
                ):
                    raise ValueError(
                        "Butun, Yarim va Chorak narxlarini kiriting"
                    )

            elif s in {
                "Kompot va Ayron",
                "Salqin ichimliklar",
            }:
                if any(
                    field.value() <= 0
                    for field in self.liter_prices.values()
                ):
                    raise ValueError(
                        "0.5, 1, 1.5 va 2 litr narxlarini kiriting"
                    )

            elif (
                not manual
                and self.price.value() <= 0
            ):
                raise ValueError(
                    "Narxni kiriting"
                )

            if s == "Jizz":
                unit = "AMOUNT"
                base_price = 0
                volume = None

            elif s == "Osh":
                unit = "PORTION"
                base_price = 0
                volume = None

            elif s in {
                "Shurva",
                "Ko‘za shurva",
                "Mastava",
            }:
                unit = "PORTION"
                base_price = self.price.value()
                volume = None

            elif s in {
                "Manti",
                "Salatlar",
                "Choy va Novot",
            }:
                unit = "PIECE"
                base_price = self.price.value()
                volume = None

            elif s == "Nonlar":
                unit = "PIECE"
                base_price = 0
                volume = None

            elif s in {
                "Kompot va Ayron",
                "Salqin ichimliklar",
            }:
                unit = "LITER"
                base_price = 0
                volume = None

            else:
                raise ValueError(
                    "Mahsulot turi aniqlanmadi"
                )

            self.client.request(
                "PATCH",
                f"/api/products/{self.original['id']}",
                {
                    "category_id": self.original[
                        "category_id"
                    ],
                    "name": name,
                    "image_path": self.image_path,
                    "volume_liters": volume,
                    "unit_type": unit,
                    "base_price": base_price,
                    "allows_manual_price": manual,
                    "is_active": self.original.get(
                        "is_active",
                        True,
                    ),
                },
            )

            if s == "Osh":
                self.client.save_price_options(
                    self.original["id"],
                    [
                        {
                            "name": label,
                            "quantity": value,
                            "price": self.osh_prices[label].value(),
                        }
                        for label, value in OSH_PORTIONS
                        if self.osh_prices[label].value() > 0
                    ],
                )

            if s == "Nonlar":
                quantities = {
                    "Butun": "1",
                    "Yarim": "0.5",
                    "Chorak": "0.25",
                }

                self.client.save_price_options(
                    self.original["id"],
                    [
                        {
                            "name": label,
                            "quantity": quantities[label],
                            "price": self.bread_prices[label].value(),
                        }
                        for label, _value in BREAD
                    ],
                )

            if s in {
                "Kompot va Ayron",
                "Salqin ichimliklar",
            }:
                self.client.save_price_options(
                    self.original["id"],
                    [
                        {
                            "name": label,
                            "quantity": value,
                            "price": self.liter_prices[label].value(),
                        }
                        for label, value in LITERS
                    ],
                )

            if manual:
                self._replace_presets()

            self.saved = True
            self.accept()

        except Exception as error:
            self.on_error(error)


def edit_strict_record(
    client,
    record,
    on_error,
    parent=None,
):
    resource = record.get(
        "_strict_resource",
        "products",
    )

    categories = client.list_records(
        "categories"
    )

    if resource == "addons":
        key = _category_key(
            record.get("name")
        )

        addon_types = {
            "tuxum": "Tuxum",
            "tuxum1": "Tuxum",
            "bedanatuxum": "Bedana tuxum",
            "qazi": "Qazi",
            "gosht": "Go‘sht",
        }

        selection = addon_types.get(key)

        if not selection:
            raise ValueError(
                "Bu qo‘shimcha qat’iy menyu turiga kirmaydi"
            )

        milliy = next(
            (
                row
                for row in categories
                if _category_key(
                    row.get("name")
                )
                == "milliytaomlar"
            ),
            None,
        )

        if not milliy:
            raise ValueError(
                "Milliy taomlar guruhi topilmadi"
            )

        dialog = StrictEditDialog(
            client,
            selection,
            milliy,
            record,
            on_error,
            parent,
            resource="addons",
        )

    else:
        selection = product_selection(
            record,
            categories,
        )

        category = next(
            (
                row
                for row in categories
                if row["id"]
                == record.get("category_id")
            ),
            None,
        )

        if not category:
            raise ValueError(
                "Mahsulot guruhi topilmadi"
            )

        dialog = StrictEditDialog(
            client,
            selection,
            category,
            record,
            on_error,
            parent,
            resource="products",
        )

    return (
        dialog.exec()
        == QDialog.DialogCode.Accepted
        and dialog.saved
    )
