from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from app.ui.state import Cart, format_money


class CartWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("JORIY BUYURTMA")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        layout.addWidget(title)
        self.items = QListWidget()
        self.items.setWordWrap(True)
        layout.addWidget(self.items, 1)
        buttons = QHBoxLayout()
        self.minus_button = QPushButton("−")
        self.plus_button = QPushButton("+")
        self.edit_button = QPushButton("Tahrirlash")
        for button in (self.minus_button, self.plus_button, self.edit_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        buttons = QHBoxLayout()
        self.remove_button = QPushButton("Tanlanganni o‘chirish")
        self.clear_button = QPushButton("Savatni tozalash")
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.clear_button)
        layout.addLayout(buttons)
        self.total_label = QLabel("JAMI: 0 so‘m")
        self.total_label.setObjectName("totalLabel")
        layout.addWidget(self.total_label)

    def render(self, cart: Cart) -> None:
        self.items.clear()
        for item in cart.items:
            price_text = format_money(item.unit_price)
            variant = f" · {item.option_name}" if item.option_name else ""
            text = f"{item.name}{variant} × {item.quantity:g}\n{price_text} = {format_money(item.product_total)}"
            if item.addons:
                text += "\n" + "\n".join(
                    f"  + {addon.name} × {addon.quantity:.3f}: {format_money(addon.total_price)}"
                    for addon in item.addons
                )
            text += f"\nJami: {format_money(item.total_price)}"
            self.items.addItem(text)
        self.total_label.setText(f"JAMI: {format_money(cart.total_amount)}")
