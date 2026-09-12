from decimal import Decimal
from PySide6.QtWidgets import QDialog, QGridLayout, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from app.ui.state import format_money


class NumberDialog(QDialog):
    """Integer UZS keypad; presets come from the authenticated catalog."""
    def __init__(self, title="Qo‘lda narx", presets=(), initial=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.digits = str(initial) if initial else ""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        preset_grid = QGridLayout()
        for index, preset in enumerate(presets):
            if not preset.get("is_active", True):
                continue
            amount = int(preset["amount"])
            button = QPushButton(format_money(amount))
            button.clicked.connect(lambda _=False, value=amount: self._preset(value))
            preset_grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(preset_grid)
        other = QPushButton("BOSHQA NARX")
        other.clicked.connect(lambda: self._press("C"))
        layout.addWidget(other)
        self.display = QLabel()
        self.display.setObjectName("totalLabel")
        layout.addWidget(self.display)
        grid = QGridLayout()
        for index, text in enumerate(("1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫")):
            button = QPushButton(text)
            button.setMinimumHeight(56)
            button.clicked.connect(lambda _=False, value=text: self._press(value))
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        actions = QHBoxLayout()
        cancel = QPushButton("BEKOR")
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton("TASDIQLASH")
        self.confirm.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        layout.addLayout(actions)
        self._refresh()

    @property
    def amount(self):
        return int(self.digits or "0")

    def _preset(self, amount):
        self.digits = str(amount)
        self._refresh()

    def _press(self, text):
        if text == "C":
            self.digits = ""
        elif text == "⌫":
            self.digits = self.digits[:-1]
        elif len(self.digits) < 9:
            self.digits = (self.digits + text).lstrip("0")
        self._refresh()

    def _refresh(self):
        self.display.setText(format_money(self.amount))
        self.confirm.setEnabled(self.amount > 0)

    def accept(self):
        if self.amount > 0:
            super().accept()

    @classmethod
    def money(cls, parent=None, title="Qo‘lda narx", presets=(), initial=0):
        dialog = cls(title, presets, initial, parent)
        return dialog.amount if dialog.exec() == QDialog.DialogCode.Accepted else None

    @classmethod
    def quantity(cls, parent=None, initial=1):
        dialog = cls("Miqdor", initial=int(initial), parent=parent)
        return Decimal(dialog.amount) if dialog.exec() == QDialog.DialogCode.Accepted else None
