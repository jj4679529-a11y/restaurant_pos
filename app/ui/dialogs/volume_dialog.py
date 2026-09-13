"""Decimal volume entry; money still uses its separate integer keypad."""
from decimal import Decimal
import re
from PySide6.QtWidgets import QDialog, QVBoxLayout, QGridLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton
from app.ui.state import format_quantity


def parse_volume(text: str) -> Decimal:
    normalized = text.strip().replace(',', '.')
    if not re.fullmatch(r'\d{1,9}(?:\.\d{1,3})?', normalized):
        raise ValueError('Hajmni kiriting: masalan, 1.5 L (ko‘pi bilan 3 kasr xona)')
    value = Decimal(normalized)
    if value <= 0:
        raise ValueError('Hajm noldan katta bo‘lishi kerak')
    return value


class VolumeDialog(QDialog):
    def __init__(self, initial=Decimal(1), parent=None):
        super().__init__(parent)
        self.setWindowTitle('Hajm kiriting')
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Hajm kiriting · L'))
        self.input = QLineEdit(format_quantity(initial))
        self.input.setMaxLength(13)
        self.input.selectAll()
        layout.addWidget(self.input)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        grid = QGridLayout()
        for index, text in enumerate(('1', '2', '3', '4', '5', '6', '7', '8', '9', 'C', '0', '.')):
            button = QPushButton(text)
            button.setMinimumHeight(48)
            button.clicked.connect(lambda _=False, value=text: self.press(value))
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        back = QPushButton('⌫')
        back.clicked.connect(self.input.backspace)
        layout.addWidget(back)
        actions = QHBoxLayout()
        cancel = QPushButton('BEKOR')
        cancel.clicked.connect(self.reject)
        self.confirm = QPushButton('TASDIQLASH')
        self.confirm.setProperty('primary', True)
        self.confirm.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(self.confirm)
        layout.addLayout(actions)
        self.input.textChanged.connect(self.validate)
        self.validate()

    def press(self, text):
        self.input.clear() if text == 'C' else self.input.insert(text)

    def validate(self):
        try:
            parse_volume(self.input.text())
        except ValueError as error:
            self.error.setText(str(error))
            self.confirm.setEnabled(False)
        else:
            self.error.clear()
            self.confirm.setEnabled(True)

    def accept(self):
        self.validate()
        if self.confirm.isEnabled():
            super().accept()

    @classmethod
    def choose(cls, initial=Decimal(1), parent=None):
        dialog = cls(initial, parent)
        return parse_volume(dialog.input.text()) if dialog.exec() == QDialog.DialogCode.Accepted else None
