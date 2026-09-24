from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QToolButton

from app.ui.state import format_money, format_quantity


def product_pixmap(image_data=None):
    """Return a true cover/center-cropped product image."""

    target_width = 332
    target_height = 200

    image = QPixmap()

    if image_data and image.loadFromData(image_data):
        scaled = image.scaled(
            target_width,
            target_height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = max(
            0,
            (scaled.width() - target_width) // 2,
        )
        y = max(
            0,
            (scaled.height() - target_height) // 2,
        )

        return scaled.copy(
            QRect(
                x,
                y,
                target_width,
                target_height,
            )
        )

    placeholder = QPixmap(
        target_width,
        target_height,
    )
    placeholder.fill(
        QColor("#eef2f3")
    )

    painter = QPainter(placeholder)
    painter.setPen(
        QColor("#a8b5b5")
    )
    painter.drawEllipse(
        108,
        54,
        116,
        92,
    )
    painter.drawEllipse(
        128,
        69,
        76,
        62,
    )
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
        available = product.get('is_active', True)
        title = product['name']
        if product.get('volume_liters'):
            title += '\n' + format_quantity(product['volume_liters']) + ' L'
        if available:
            self.setText(f"{title}\n{price}")
        else:
            self.setText(f"{title}\nMavjud emas")
        self.setEnabled(available)
        self.setProperty('role', 'product-card')
        self.setIcon(QIcon(product_pixmap(image_data)))
        self.setIconSize(QSize(166, 100))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setMinimumSize(164, 172)
        self.setSizePolicy(self.sizePolicy().Policy.Expanding, self.sizePolicy().Policy.Fixed)
        self.setFixedHeight(196 if product.get('volume_liters') else 180)
        self.setToolTip(self.text())
        self.setObjectName("productCard")
