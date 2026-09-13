from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QToolButton

from app.ui.state import format_money


def product_pixmap(image_data=None):
    image = QPixmap()
    if image_data and image.loadFromData(image_data):
        return image.scaled(180, 108, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    placeholder = QPixmap(180, 108)
    placeholder.fill(QColor("#eef2f3"))
    painter = QPainter(placeholder)
    painter.setPen(QColor("#a8b5b5"))
    painter.drawEllipse(58, 22, 64, 64)
    painter.drawEllipse(68, 32, 44, 44)
    painter.end()
    return placeholder


class ProductCard(QToolButton):
    def __init__(self, product, image_data=None, parent=None):
        super().__init__(parent)
        options = [o for o in product.get("price_options", []) if o.get("is_active", True)]
        if options:
            price = format_money(min(o["price"] for o in options)) + " dan"
        elif product.get("allows_manual_price"):
            price = "Narxni tanlash"
        elif product.get("base_price", 0) > 0:
            price = format_money(product["base_price"])
            if product.get('unit_type') == 'LITER':
                price += ' / litr'
        else:
            price = "Narx sozlanmagan"
        self.setText(f"{product['name']}\n{price}")
        self.setIcon(QIcon(product_pixmap(image_data)))
        self.setIconSize(QSize(132, 80))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setMinimumSize(140, 148)
        self.setSizePolicy(self.sizePolicy().Policy.Expanding, self.sizePolicy().Policy.Fixed)
        self.setFixedHeight(156)
        self.setToolTip(self.text())
        self.setObjectName("productCard")
