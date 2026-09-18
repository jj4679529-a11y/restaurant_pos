"""Restaurant-facing editors over the existing catalog API."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QFormLayout,
    QDialog,
    QScrollArea,
    QMessageBox,
    QScroller,
)

from app.ui.admin.api import menu_name
from app.ui.admin.forms import Editor
from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.state import format_money


class QuickPricesDialog(QDialog):
    def __init__(self, client, resource, target, on_error, parent=None):
        super().__init__(parent)

        self.client = client
        self.target = target
        self.on_error = on_error
        self.field = "product_id" if resource == "products" else "addon_id"
        self.records = []

        self.setWindowTitle(target["name"] + " — Tezkor narxlar")
        self.resize(720, 620)

        layout = QVBoxLayout(self)

        title = QLabel(target["name"])
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        subtitle = QLabel("Kassir ekrani uchun 4 tagacha tezkor narx belgilang")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        QScroller.grabGesture(
            self.scroll.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        content = QWidget()
        self.rows = QVBoxLayout(content)

        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)

        self.add_button = QPushButton("＋ NARX QO‘SHISH · 4 TAGACHA")
        self.add_button.setProperty("primary", True)
        self.add_button.setMinimumHeight(56)
        self.add_button.clicked.connect(lambda: self.edit())
        layout.addWidget(self.add_button)

        close = QPushButton("YOPISH")
        close.setMinimumHeight(56)
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        self.load()

    def _is_gosht(self):
        name = menu_name(self.target.get("name", ""))
        return name in {
            "gosht",
            "go'sht",
            "go‘sht",
            "goʻsht",
            "go’sht",
        }

    def load(self):
        try:
            records = [
                record
                for record in self.client.list_records("presets")
                if record.get(self.field) == self.target["id"]
            ]
        except Exception as error:
            self.on_error(error)
            return

        self.records = records

        while self.rows.count():
            item = self.rows.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        visible_records = records[:4]

        self.add_button.setEnabled(len(records) < 4)
        self.add_button.setToolTip("Ko‘pi bilan 4 ta tezkor narx")

        if not visible_records:
            empty = QLabel("Tezkor narxlar sozlanmagan")
            empty.setWordWrap(True)
            self.rows.addWidget(empty)

        for record in visible_records:
            row = QWidget()
            line = QHBoxLayout(row)

            text = format_money(record["amount"])

            if not record.get("is_active", True):
                text += " · Nofaol"

            label = QLabel(text)
            line.addWidget(label, 1)

            edit = QPushButton("Tahrirlash")
            edit.setMinimumHeight(52)
            edit.clicked.connect(
                lambda _=False, current=record: self.edit(current)
            )
            line.addWidget(edit)

            toggle = QPushButton(
                "Nofaol qilish"
                if record.get("is_active", True)
                else "Faollashtirish"
            )
            toggle.setMinimumHeight(52)
            toggle.clicked.connect(
                lambda _=False, current=record: self.toggle(current)
            )
            line.addWidget(toggle)

            self.rows.addWidget(row)

        self.rows.addStretch()

    def edit(self, original=None):
        if original is None and len(self.records) >= 4:
            QMessageBox.warning(
                self,
                "Cheklov",
                "Ko‘pi bilan 4 ta tezkor narx kiritish mumkin.",
            )
            return

        amount = NumberDialog.money(
            self,
            "Tezkor narx",
            initial=(original or {}).get("amount", 0),
        )

        if amount is None:
            return

        if amount <= 0:
            QMessageBox.warning(
                self,
                "Noto‘g‘ri narx",
                "Narx 0 dan katta bo‘lishi kerak.",
            )
            return

        if self._is_gosht() and amount < 5000:
            QMessageBox.warning(
                self,
                "Noto‘g‘ri narx",
                "Go‘sht narxi kamida 5 000 so‘m bo‘lishi kerak.",
            )
            return

        try:
            data = {
                "amount": amount,
            }

            if original is None:
                data[self.field] = self.target["id"]

            self.client.save_record(
                "presets",
                data,
                original,
            )

            self.load()

        except Exception as error:
            self.on_error(error)

    def toggle(self, record):
        answer = QMessageBox.question(
            self,
            "Tasdiqlash",
            "Tezkor narx faolligini o‘zgartirasizmi?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.client.save_record(
                "presets",
                {
                    "is_active": not record.get("is_active", True),
                },
                record,
            )

            self.load()

        except Exception as error:
            self.on_error(error)


class OshPage(QWidget):
    def __init__(self, client, on_error, parent=None):
        super().__init__(parent)

        self.client = client
        self.on_error = on_error
        self.product = None
        self.initial = (0, 0)

        root = QVBoxLayout(self)

        title = QLabel("Osh — porsiya va qo‘shimchalar")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        portion_title = QLabel("PORSIYALAR")
        portion_title.setObjectName("sectionTitle")
        root.addWidget(portion_title)

        portion_help = QLabel(
            "Kassir Oshni tanlaganda shu porsiya va narxlar ko‘rinadi."
        )
        portion_help.setWordWrap(True)
        root.addWidget(portion_help)

        form = QFormLayout()
        self.prices = {}

        for key, label_text in [
            ("half_price", "0.5 porsiya"),
            ("full_price", "1 porsiya"),
        ]:
            row = QHBoxLayout()

            spin = QSpinBox()
            spin.setRange(0, 2_147_483_647)
            spin.setSuffix(" so‘m")
            spin.setMinimumHeight(52)

            self.prices[key] = spin
            row.addWidget(spin, 1)

            keypad = QPushButton("NARX")
            keypad.setMinimumHeight(52)
            keypad.clicked.connect(
                lambda _=False, field=spin: self.number(field)
            )

            row.addWidget(keypad)

            form.addRow(label_text, row)

        root.addLayout(form)

        self.save_button = QPushButton("PORSIYA NARXLARINI SAQLASH")
        self.save_button.setProperty("primary", True)
        self.save_button.setMinimumHeight(60)
        self.save_button.clicked.connect(self.save)

        root.addWidget(self.save_button)

        self.notice = QLabel(
            "Tuxum, Bedana tuxum va Qazi — dona narxi. "
            "Go‘sht — 4 ta tezkor narx + kassirda boshqa narx."
        )
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        QScroller.grabGesture(
            self.scroll.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        content = QWidget()
        self.addons = QVBoxLayout(content)

        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

    def number(self, field):
        amount = NumberDialog.money(
            self,
            "Porsiya narxi",
            initial=field.value(),
        )

        if amount is not None:
            field.setValue(amount)

    def load(self):
        try:
            products = self.client.list_records("products")

            product = next(
                (
                    item
                    for item in products
                    if menu_name(item["name"]) == "osh"
                    and item.get("is_active", True)
                ),
                None,
            )

            self.product = product
            self.save_button.setEnabled(product is not None)

            if product is None:
                self.notice.setText(
                    "Faol Osh topilmadi. Avval Menyu bo‘limida Osh yarating yoki faollashtiring."
                )
                self._clear_addons()
                return

            for key, option_name in [
                ("half_price", "0.5 porsiya"),
                ("full_price", "1 porsiya"),
            ]:
                price = next(
                    (
                        option["price"]
                        for option in product.get("price_options", [])
                        if option.get("name") == option_name
                        and option.get("is_active", True)
                    ),
                    0,
                )

                self.prices[key].setValue(price)

            self.initial = tuple(
                field.value()
                for field in self.prices.values()
            )

            self._clear_addons()

            addons = product.get(
                "available_addons",
                [],
            )

            if not addons:
                empty = QLabel("Osh uchun qo‘shimchalar topilmadi.")
                self.addons.addWidget(empty)

            for addon in addons:
                row = QWidget()
                line = QHBoxLayout(row)

                name = QLabel(addon["name"])
                line.addWidget(name, 1)

                manual = addon.get(
                    "allows_manual_price",
                    False,
                )

                if manual:
                    price_text = "4 ta tezkor narx + boshqa narx"
                else:
                    price_text = (
                        format_money(
                            addon.get("base_price", 0)
                        )
                        + " / dona"
                    )

                price_label = QLabel(price_text)
                line.addWidget(price_label)

                edit = QPushButton(
                    "TEZKOR NARXLAR"
                    if manual
                    else "DONA NARXINI O‘ZGARTIRISH"
                )

                edit.setMinimumHeight(52)

                edit.clicked.connect(
                    lambda _=False, current=addon: self.edit_addon(current)
                )

                line.addWidget(edit)

                self.addons.addWidget(row)

            self.addons.addStretch()

        except Exception as error:
            self.on_error(error)

    def _clear_addons(self):
        while self.addons.count():
            item = self.addons.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

    def can_leave(self):
        current = tuple(
            field.value()
            for field in self.prices.values()
        )

        if current == self.initial:
            return True

        answer = QMessageBox.question(
            self,
            "Saqlanmagan narxlar",
            "Narxlarni saqlamasdan chiqasizmi?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        return answer == QMessageBox.StandardButton.Yes

    def save(self):
        if not self.product:
            return

        try:
            data = {
                key: field.value()
                for key, field in self.prices.items()
            }

            if not all(data.values()):
                raise ValueError(
                    "Ikkala porsiya narxini kiriting"
                )

            self.client.save_osh_prices(
                self.product["id"],
                **data,
            )

            self.initial = tuple(
                field.value()
                for field in self.prices.values()
            )

            self.notice.setText(
                "✓ Porsiya narxlari saqlandi."
            )

        except Exception as error:
            self.on_error(error)

    def edit_addon(self, addon):
        draft = {
            key: field.value()
            for key, field in self.prices.items()
        }

        initial = self.initial

        if addon.get("allows_manual_price", False):
            dialog = QuickPricesDialog(
                self.client,
                "addons",
                addon,
                self.on_error,
                self,
            )
            dialog.exec()

        else:
            def save(data):
                self.client.save_record(
                    "addons",
                    {
                        "name": addon["name"],
                        **data,
                    },
                    addon,
                )

            editor = Editor(
                addon["name"],
                [
                    (
                        "base_price",
                        "Dona narxi",
                        "money",
                    )
                ],
                addon,
                save,
                self.on_error,
                self,
            )

            editor.exec()

        self.load()

        for key, value in draft.items():
            self.prices[key].setValue(value)

        self.initial = initial