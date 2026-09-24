from decimal import Decimal, InvalidOperation
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QScroller
from PySide6.QtCore import QSize, Qt
from app.ui.admin.forms import Editor
from app.ui.state import format_money


class PortionsDialog(QDialog):
    def __init__(self, client, product, on_error, parent=None):
        super().__init__(parent)
        self.client, self.product, self.on_error = client, product, on_error
        self.setWindowTitle(product['name'] + ' — Porsiyalar / Butun, Yarim, Chorak')
        self.resize(680, 550)
        layout = QVBoxLayout(self)
        self.rows = QListWidget()
        self.rows.setObjectName("portionsList")
        self.rows.setSpacing(5)

        QScroller.grabGesture(
            self.rows.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        layout.addWidget(self.rows)
        actions = QHBoxLayout()
        for title, callback in [('+ QO‘SHISH', lambda: self.edit()), ('TAHRIRLASH', self.edit_selected), ('YOPISH', self.accept)]:
            button = QPushButton(title)
            button.setMinimumHeight(64)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.load()

    def load(self):
        try:
            records = self.client._all_pages(f'/api/products/{self.product["id"]}/price-options')
            self.rows.clear()
            for record in records:
                item = QListWidgetItem(
                    f"{record['name']} — {format_money(record['price'])}"
                    + ('' if record['is_active'] else ' · Nofaol')
                )
                item.setSizeHint(QSize(0, 72))
                self.rows.addItem(item)
                self.rows.item(self.rows.count() - 1).setData(Qt.ItemDataRole.UserRole, record)
        except Exception as error:
            self.on_error(error)

    def edit_selected(self):
        if self.rows.currentItem():
            self.edit(self.rows.currentItem().data(Qt.ItemDataRole.UserRole))

    def edit(self, original=None):
        def save(data):
            try:
                quantity = Decimal(data['quantity'].replace(',', '.'))
            except InvalidOperation:
                raise ValueError('Miqdorni raqam bilan kiriting') from None
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError('Miqdor musbat bo‘lishi kerak')
            data['quantity'] = str(quantity)
            path = f'/api/price-options/{original["id"]}' if original else f'/api/products/{self.product["id"]}/price-options'
            self.client.request('PATCH' if original else 'POST', path, data)
        dialog = Editor('Porsiya / non varianti', [('name', 'Nomi (Butun / Yarim / Chorak)', 'text'),
                        ('quantity', 'Porsiya miqdori', 'text'), ('price', 'Narxi', 'money'),
                        ('is_active', 'Faol', 'bool')], original or {'quantity': '1'}, save, self.on_error, self)
        if dialog.exec():
            self.load()
