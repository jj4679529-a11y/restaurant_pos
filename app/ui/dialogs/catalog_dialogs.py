from decimal import Decimal
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.dialogs.number_dialog import NumberDialog
from app.ui.state import CartAddOn, format_money


class PriceOptionDialog(QDialog):
    def __init__(self, options: list[dict[str, Any]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Narxni tanlang")
        self.setMinimumSize(360, 360)
        self.selected_option: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("PriceOption tanlang"))
        self.list_widget = QListWidget()
        for option in options:
            item = QListWidgetItem(f"{option['name']} — {format_money(int(option['price']))}")
            item.setData(Qt.ItemDataRole.UserRole, option)
            item.setSizeHint(item.sizeHint().expandedTo(item.sizeHint()))
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._select)
        layout.addWidget(self.list_widget)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select(self, item: QListWidgetItem) -> None:
        self.selected_option = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _accept_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None:
            self._select(item)

    @classmethod
    def choose(cls, options: list[dict[str, Any]], parent=None) -> dict[str, Any] | None:
        dialog = cls(options, parent)
        return dialog.selected_option if dialog.exec() == QDialog.DialogCode.Accepted else None


class AddOnDialog(QDialog):
    def __init__(self, addons: list[dict[str, Any]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Qo‘shimchalarni tanlang")
        self.setMinimumSize(420, 420)
        self._addons = addons
        self._checkboxes: dict[int, QCheckBox] = {}
        self._manual_prices: dict[int, int] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Kerakli qo‘shimchalarni belgilang"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for addon in addons:
            has_manual_price = bool(addon.get("allows_manual_price"))
            has_configured_price = int(addon.get("base_price", 0)) > 0
            if has_manual_price:
                suffix = " — qo‘lda narx"
            elif has_configured_price:
                suffix = f" — {format_money(int(addon['base_price']))}"
            else:
                suffix = " — narx sozlanmagan"
            checkbox = QCheckBox(f"{addon['name']}{suffix}")
            checkbox.setMinimumHeight(48)
            checkbox.setChecked(bool(addon.get("is_required")))
            checkbox.setEnabled(not bool(addon.get("is_required")) and (has_manual_price or has_configured_price))
            checkbox.toggled.connect(lambda checked, value=addon: self._on_toggled(value, checked))
            self._checkboxes[int(addon["id"])] = checkbox
            content_layout.addWidget(checkbox)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_toggled(self, addon: dict[str, Any], checked: bool) -> None:
        addon_id = int(addon["id"])
        if not checked:
            self._manual_prices.pop(addon_id, None)
            return
        if addon.get("allows_manual_price"):
            price = NumberDialog.money(self, f"{addon['name']} narxi")
            if price is None:
                self._checkboxes[addon_id].setChecked(False)
            else:
                self._manual_prices[addon_id] = price

    def selected_addons(self) -> tuple[CartAddOn, ...]:
        selected: list[CartAddOn] = []
        for addon in self._addons:
            addon_id = int(addon["id"])
            if not self._checkboxes[addon_id].isChecked():
                continue
            manual_price = self._manual_prices.get(addon_id)
            selected.append(
                CartAddOn(
                    addon_id=addon_id,
                    name=str(addon["name"]),
                    quantity=Decimal("1.000"),
                    unit_price=manual_price if manual_price is not None else int(addon["base_price"]),
                    manual_price=manual_price,
                )
            )
        return tuple(selected)

    @classmethod
    def choose(cls, addons: list[dict[str, Any]], parent=None) -> tuple[CartAddOn, ...] | None:
        if not addons:
            return ()
        dialog = cls(addons, parent)
        return dialog.selected_addons() if dialog.exec() == QDialog.DialogCode.Accepted else None
