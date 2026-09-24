from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScroller,
    QVBoxLayout,
    QWidget,
)

from app.ui.state import Cart, format_money, format_quantity


class CartWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("panel")
        self.setProperty("role", "order-card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("JORIY BUYURTMA")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.empty = QLabel(
            "Mahsulot tanlang\n"
            "Buyurtma shu yerda ko‘rinadi"
        )
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

        self.items = QListWidget()
        self.items.setObjectName("receiptList")
        self.items.setWordWrap(True)
        self.items.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.items.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.items.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )

        self.items.currentRowChanged.connect(self._selection)

        palette = self.items.palette()

        for role in (
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Window,
        ):
            palette.setColor(role, QColor("#ffffff"))

        palette.setColor(
            QPalette.ColorRole.Text,
            QColor("#253934"),
        )

        self.items.setPalette(palette)
        self.items.viewport().setPalette(palette)
        self.items.viewport().setAutoFillBackground(True)

        QScroller.grabGesture(
            self.items.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        layout.addWidget(self.items, 1)

        # Controller bilan eski ulanishlar saqlanadi.
        # Bu tugmalar ko‘rinmaydi, lekin main_window.py
        # ularga signal orqali murojaat qilishda davom etadi.
        self.minus_button = QPushButton("−")
        self.plus_button = QPushButton("+")
        self.edit_button = QPushButton("Tahrirlash")
        self.remove_button = QPushButton("Tanlanganni o‘chirish")

        for button in (
            self.minus_button,
            self.plus_button,
            self.edit_button,
            self.remove_button,
        ):
            button.setParent(self)
            button.hide()

        bottom = QHBoxLayout()

        self.clear_button = QPushButton("Savatni tozalash")
        self.clear_button.setParent(self)
        self.clear_button.hide()

        # Compatibility layout remains, but current order is receipt-only.
        layout.addLayout(bottom)

        self.total_label = QLabel("JAMI: 0 so‘m")
        self.total_label.setObjectName("totalLabel")

        layout.addWidget(self.total_label)

    def _selection(self, selected):
        for index in range(self.items.count()):
            card = self.items.itemWidget(
                self.items.item(index)
            )

            if card:
                card.setProperty(
                    "selected",
                    index == selected,
                )

                card.style().unpolish(card)
                card.style().polish(card)

    def _select_row(self, row_index: int) -> None:
        self.items.setCurrentRow(row_index)
        self._selection(row_index)

    def _trigger_plus(self, row_index: int) -> None:
        self._select_row(row_index)
        self.plus_button.click()

    def _trigger_minus(self, row_index: int) -> None:
        self._select_row(row_index)
        self.minus_button.click()

    def _trigger_edit(self, row_index: int) -> None:
        self._select_row(row_index)
        self.edit_button.click()

    def render(self, cart: Cart) -> None:
        self.items.clear()
        self.empty.setVisible(not cart.items)

        for index, item in enumerate(cart.items):
            liter = item.unit_type == "LITER"

            if liter:
                title = (
                    f"{item.name} — "
                    f"{format_quantity(item.quantity)} L"
                )

            elif item.option_name:
                title = (
                    f"{item.name} — "
                    f"{item.option_name}"
                )

                if item.quantity != 1:
                    title += (
                        f" × {format_quantity(item.quantity)}"
                    )

            else:
                title = item.name

                if item.quantity != 1:
                    title += (
                        f" × {format_quantity(item.quantity)}"
                    )

            accessible_text = (
                f"{title}: "
                f"{format_money(item.product_total)}"
            )

            for addon in item.addons:
                if (
                    addon.manual_price is not None
                    and addon.quantity == 1
                ):
                    addon_name = f"+ {addon.name}"
                else:
                    addon_name = (
                        f"+ {addon.name} "
                        f"×{format_quantity(addon.quantity)}"
                    )

                accessible_text += (
                    f"\n{addon_name}: "
                    f"{format_money(addon.total_price)}"
                )

            row = QListWidgetItem()

            row.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                accessible_text,
            )

            base_height = 54
            addon_height = len(item.addons) * 26
            liter_height = 0

            row.setSizeHint(
                QSize(
                    0,
                    base_height
                    + addon_height
                    + liter_height,
                )
            )

            self.items.addItem(row)

            content = QWidget()
            content.setObjectName("receiptCard")

            content.setAttribute(
                Qt.WidgetAttribute.WA_StyledBackground,
                True,
            )

            content.setPalette(
                self.items.palette()
            )

            box = QVBoxLayout(content)

            box.setContentsMargins(
                8,
                5,
                8,
                5,
            )

            box.setSpacing(3)

            def money_row(
                name,
                total,
                main=False,
            ):
                line = QHBoxLayout()
                line.setSpacing(6)

                label = QLabel(name)
                label.setWordWrap(True)

                label.setObjectName(
                    "receiptTitle"
                    if main
                    else "receiptSecondary"
                )

                price = QLabel(
                    format_money(total)
                )

                price.setObjectName(
                    "receiptTitle"
                    if main
                    else "receiptSecondary"
                )

                price.setAlignment(
                    Qt.AlignmentFlag.AlignRight
                    | Qt.AlignmentFlag.AlignVCenter
                )

                line.addWidget(
                    label,
                    1,
                )

                line.addWidget(
                    price,
                )

                box.addLayout(
                    line
                )

            money_row(
                title,
                item.product_total,
                True,
            )

            for addon in item.addons:
                if (
                    addon.manual_price is not None
                    and addon.quantity == 1
                ):
                    addon_name = (
                        f"+ {addon.name}"
                    )

                else:
                    addon_name = (
                        f"+ {addon.name} "
                        f"×{format_quantity(addon.quantity)}"
                    )

                money_row(
                    addon_name,
                    addon.total_price,
                )


            # --------------------------------------------------
            # Hidden compatibility widgets.
            #
            # Receipt UI remains display-only, but older controller
            # connections/tests still expect these child widgets.
            # They are never shown to the cashier.
            # --------------------------------------------------

            compat_quantity = QLabel(
                format_quantity(item.quantity),
                content,
            )
            compat_quantity.setObjectName(
                "receiptCompatibilityQuantity"
            )
            compat_quantity.hide()

            compat_rate = QLabel(
                (
                    format_money(item.unit_price)
                    + " / litr"
                )
                if liter
                else "",
                content,
            )
            compat_rate.setObjectName(
                "receiptCompatibilityRate"
            )
            compat_rate.hide()

            # Legacy +/- compatibility is only needed for
            # non-liter products. Liter products never use +/-.
            if not liter:
                compat_minus = QPushButton(
                    "−",
                    content,
                )
                compat_plus = QPushButton(
                    "+",
                    content,
                )

                compat_minus.clicked.connect(
                    lambda checked=False, i=index:
                    self._trigger_minus(i)
                )

                compat_plus.clicked.connect(
                    lambda checked=False, i=index:
                    self._trigger_plus(i)
                )

                compat_minus.hide()
                compat_plus.hide()

            compat_edit = QPushButton(
                "SOZLASH",
                content,
            )
            compat_edit.clicked.connect(
                lambda checked=False, i=index:
                self._trigger_edit(i)
            )
            compat_edit.hide()

            self.items.setItemWidget(
                row,
                content,
            )

        self.total_label.setText(
            f"JAMI: {format_money(cart.total_amount)}"
        )