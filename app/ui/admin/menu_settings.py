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


def _is_osh_name(value):
    key = menu_name(value or "")
    return key == "osh" or key.endswith(" osh")


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
        self.add_button.setMinimumHeight(64)
        self.add_button.clicked.connect(lambda: self.edit())
        layout.addWidget(self.add_button)

        close = QPushButton("YOPISH")
        close.setMinimumHeight(64)
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
            row.setObjectName("pricePresetCard")
            line = QHBoxLayout(row)
            line.setContentsMargins(14, 10, 14, 10)
            line.setSpacing(10)

            text = format_money(record["amount"])

            if not record.get("is_active", True):
                text += " · Nofaol"

            label = QLabel(text)
            label.setObjectName("pricePresetValue")
            line.addWidget(label, 1)

            edit = QPushButton("Tahrirlash")
            edit.setMinimumHeight(60)
            edit.clicked.connect(
                lambda _=False, current=record: self.edit(current)
            )
            line.addWidget(edit)

            toggle = QPushButton(
                "Nofaol qilish"
                if record.get("is_active", True)
                else "Faollashtirish"
            )
            toggle.setMinimumHeight(60)
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
