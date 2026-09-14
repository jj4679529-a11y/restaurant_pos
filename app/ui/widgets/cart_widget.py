from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from app.ui.state import Cart, format_money, format_quantity


class CartWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('panel')
        self.setProperty('role', 'order-card')
        layout = QVBoxLayout(self)
        title = QLabel("JORIY BUYURTMA")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.empty = QLabel('Mahsulot tanlang\nBuyurtma shu yerda ko‘rinadi')
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.items = QListWidget()
        self.items.setObjectName('receiptList')
        palette = self.items.palette()
        for role in (QPalette.ColorRole.Base, QPalette.ColorRole.Window):
            palette.setColor(role, QColor('#ffffff'))
        palette.setColor(QPalette.ColorRole.Text, QColor('#253934'))
        self.items.setPalette(palette)
        self.items.viewport().setPalette(palette)
        self.items.viewport().setAutoFillBackground(True)
        self.items.currentRowChanged.connect(self._selection)
        self.items.setWordWrap(True)
        layout.addWidget(self.items, 1)
        buttons = QHBoxLayout()
        self.minus_button = QPushButton("−")
        self.plus_button = QPushButton("+")
        self.edit_button = QPushButton("Tahrirlash")
        for button in (self.minus_button, self.plus_button, self.edit_button):
            buttons.addWidget(button)
        # Retain action objects as a single binding to existing controller logic.
        # Visible controls are attached to their own receipt line below.
        for button in (self.minus_button, self.plus_button, self.edit_button):
            button.setParent(self)
            button.hide()
        buttons = QHBoxLayout()
        self.remove_button = QPushButton("Tanlanganni o‘chirish")
        self.clear_button = QPushButton("Savatni tozalash")
        self.remove_button.setParent(self)
        self.remove_button.hide()
        buttons.addWidget(self.clear_button)
        layout.addLayout(buttons)
        self.total_label = QLabel("JAMI: 0 so‘m")
        self.total_label.setObjectName("totalLabel")
        layout.addWidget(self.total_label)

    def _selection(self, selected):
        for index in range(self.items.count()):
            card = self.items.itemWidget(self.items.item(index))
            if card:
                card.setProperty('selected', index == selected)
                card.style().unpolish(card)
                card.style().polish(card)

    def render(self, cart: Cart) -> None:
        for index in range(self.items.count()):
            previous = self.items.itemWidget(self.items.item(index))
            if previous:
                previous.hide()
        self.items.clear()
        self.empty.setVisible(not cart.items)
        for index, item in enumerate(cart.items):
            liter = item.unit_type == 'LITER'
            variant = f" — {format_quantity(item.quantity)} L" if liter else f" — {item.option_name}" if item.option_name else ''
            title = item.name + variant
            text = f'{title}: {format_money(item.product_total)}'
            row = QListWidgetItem()
            row.setData(Qt.ItemDataRole.AccessibleTextRole, text)
            # Keep accessible text on the model; the visible receipt has local actions.
            self.items.addItem(row)
            content = QWidget()
            content.setObjectName('receiptCard')
            content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            content.setPalette(self.items.palette())
            box = QVBoxLayout(content)
            box.setContentsMargins(8, 8, 8, 8)
            box.setSpacing(8)
            def money_row(name, total, main=False):
                line = QHBoxLayout()
                label = QLabel(name)
                label.setWordWrap(True)
                label.setObjectName('receiptTitle' if main else 'receiptSecondary')
                price = QLabel(format_money(total))
                price.setObjectName('receiptTitle' if main else 'receiptSecondary')
                line.addWidget(label, 1)
                line.addWidget(price)
                box.addLayout(line)
            money_row(title, item.product_total, True)
            if liter:
                rate = QLabel(format_money(item.unit_price) + ' / litr')
                rate.setObjectName('receiptSecondary')
                box.addWidget(rate)
            for addon in item.addons:
                name = f'+ {addon.name}' + ('' if addon.manual_price is not None and addon.quantity == 1 else f' ×{format_quantity(addon.quantity)}')
                money_row(name, addon.total_price)
                text += f'\n{name}: {format_money(addon.total_price)}'
            row.setData(Qt.ItemDataRole.AccessibleTextRole, text)
            actions = QHBoxLayout()
            for title, action in [('−', self.minus_button), ('+', self.plus_button),
                                  ('Tahrirlash', self.edit_button), ('×', self.remove_button)]:
                button = QPushButton(title)
                if liter and title in {'−', '+'}:
                    continue
                button.setEnabled(action.isEnabled())
                if title != 'Tahrirlash':
                    button.setFixedWidth(44)
                def invoke(_=False, i=index, target=action):
                    self.items.setCurrentRow(i)
                    target.click()
                button.clicked.connect(invoke)
                actions.addWidget(button)
                if title == '−':
                    quantity = QLabel(format_quantity(item.quantity))
                    quantity.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    actions.addWidget(quantity)
            box.addLayout(actions)
            row.setSizeHint(QSize(0, 120 + len(item.addons) * 32 + (28 if liter else 0)))
            self.items.setItemWidget(row, content)
        self.total_label.setText(f"JAMI: {format_money(cart.total_amount)}")
