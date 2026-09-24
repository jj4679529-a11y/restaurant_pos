from PySide6.QtCore import Qt, QDate, QSize
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QDateEdit,
    QPushButton,
    QTextBrowser,
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScroller,
)

from app.ui.state import format_money


class CancelledOrderDialog(QDialog):
    def __init__(self, client, order_id, on_error, parent=None):
        super().__init__(parent)

        self.client = client
        self.order_id = order_id
        self.on_error = on_error

        self.setWindowTitle("Bekor qilingan buyurtma")
        self.resize(720, 620)

        layout = QVBoxLayout(self)

        title = QLabel("BUYURTMA TAFSILOTLARI")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.text = QTextBrowser()

        QScroller.grabGesture(
            self.text.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        layout.addWidget(self.text, 1)

        close = QPushButton("YOPISH")
        close.setMinimumHeight(60)
        close.clicked.connect(self.accept)
        layout.addWidget(close)

        self.load()

    def load(self):
        try:
            order = self.client.get(
                f"/api/orders/{self.order_id}"
            )
        except Exception as error:
            self.on_error(error)
            return

        kind = (
            "CHOYXONADA"
            if order.get("order_type") == "CHAYKHANA"
            else "YETKAZIB BERISH"
        )

        lines = [
            f"Buyurtma #{order.get('order_number', '')}",
            "",
            "Holati: BEKOR QILINGAN",
            f"Turi: {kind}",
            f"Jami: {format_money(order.get('total_amount', 0))}",
        ]

        worker = order.get("delivery_worker") or {}
        if isinstance(worker, dict) and worker.get("name"):
            lines.append(
                f"Yetkazib beruvchi: {worker['name']}"
            )

        if order.get("paid_at"):
            lines.append(
                f"To‘langan vaqt: {order['paid_at']}"
            )

        if order.get("cancelled_at"):
            lines.append(
                f"Bekor qilingan vaqt: {order['cancelled_at']}"
            )

        if order.get("cancel_reason"):
            lines.append(
                f"Sabab: {order['cancel_reason']}"
            )

        canceller = (
            order.get("cancelled_by")
            or order.get("canceller")
            or {}
        )

        if isinstance(canceller, dict) and canceller.get("name"):
            lines.append(
                f"Bekor qilgan: {canceller['name']}"
            )

        lines.extend([
            "",
            "CHEK / MAHSULOTLAR",
            "─" * 32,
        ])

        for item in order.get("items", []):
            product = item.get("product") or {}

            name = (
                product.get("name")
                or item.get("product_name")
                or "Mahsulot"
            )

            lines.append(
                f"{name} × {item.get('quantity', 1)}"
                f" · {format_money(item.get('unit_price', 0))}"
                f" = {format_money(item.get('total_price', 0))}"
            )

            for addon in item.get("addons", []):
                addon_info = addon.get("addon") or {}

                lines.append(
                    f"  + {addon_info.get('name', 'Qo‘shimcha')}"
                    f" × {addon.get('quantity', 1)}"
                    f" · {format_money(addon.get('total_price', 0))}"
                )

        self.text.setPlainText(
            "\n".join(lines)
        )


class ReportsPage(QWidget):
    def __init__(self, client, on_error, parent=None):
        super().__init__(parent)

        self.client = client
        self.on_error = on_error

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Header
        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel("Hisobotlar")
        title.setObjectName("pageTitle")
        title.setStyleSheet(
            "font-size: 26px; font-weight: 800;"
        )
        title_box.addWidget(title)

        subtitle = QLabel(
            "Savdo, kassirlar va yetkazib berish bo‘yicha natijalar"
        )
        subtitle.setWordWrap(True)
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch()

        root.addLayout(header)

        # Filters
        filters = QHBoxLayout()
        filters.setSpacing(10)

        self.period = QComboBox()
        self.period.addItems(
            ["Kunlik", "Haftalik", "Oylik"]
        )
        self.period.setMinimumHeight(60)
        self.period.setMinimumWidth(140)

        self.order_type = QComboBox()
        self.order_type.addItem(
            "Umumiy",
            None,
        )
        self.order_type.addItem(
            "Choyxonada",
            "CHAYKHANA",
        )
        self.order_type.addItem(
            "Yetkazib berish",
            "DELIVERY",
        )
        self.order_type.setMinimumHeight(60)
        self.order_type.setMinimumWidth(170)

        self.date = QDateEdit(
            QDate.currentDate()
        )
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat(
            "yyyy-MM-dd"
        )
        self.date.setMinimumHeight(60)
        self.date.setMinimumWidth(150)

        load = QPushButton(
            "HISOBOTNI KO‘RISH"
        )
        load.setProperty(
            "primary",
            True,
        )
        load.setMinimumHeight(60)
        load.clicked.connect(
            lambda:
            self.load(
                self.date.date().toString(
                    "yyyy-MM-dd"
                )
            )
        )

        today = QPushButton(
            "JORIY BIZNES KUNI"
        )
        today.setMinimumHeight(60)
        today.clicked.connect(
            lambda: self.load()
        )

        filters.addWidget(
            QLabel("Davr")
        )
        filters.addWidget(
            self.period
        )

        filters.addWidget(
            QLabel("Buyurtma turi")
        )
        filters.addWidget(
            self.order_type
        )

        filters.addWidget(
            QLabel("Sana")
        )
        filters.addWidget(
            self.date
        )

        filters.addWidget(load)
        filters.addWidget(today)

        root.addLayout(filters)

        # Summary cards
        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        self.cards = {}

        cards = [
            (
                "orders",
                "Buyurtmalar",
            ),
            (
                "paid",
                "To‘langan",
            ),
            (
                "amount",
                "Jami savdo",
            ),
            (
                "delivery",
                "Yetkazib berish",
            ),
        ]

        for index, (key, card_title) in enumerate(cards):
            card = QWidget()
            card.setObjectName(
                "summaryCard"
            )

            box = QVBoxLayout(card)
            box.setContentsMargins(
                18,
                14,
                18,
                14,
            )
            box.setSpacing(5)

            label = QLabel(card_title)
            label.setObjectName(
                "summaryTitle"
            )
            box.addWidget(label)

            value = QLabel("—")
            value.setObjectName(
                "dashboardValue"
            )
            value.setStyleSheet(
                "font-size: 25px; "
                "font-weight: 800;"
            )
            value.setWordWrap(True)
            box.addWidget(value)

            cards_grid.addWidget(
                card,
                index // 2,
                index % 2,
            )

            self.cards[key] = value

        root.addLayout(cards_grid)

        # Bottom split
        body = QHBoxLayout()
        body.setSpacing(14)

        # Report details
        report_box = QVBoxLayout()

        report_title = QLabel(
            "HISOBOT TAFSILOTLARI"
        )
        report_title.setObjectName(
            "sectionTitle"
        )
        report_box.addWidget(
            report_title
        )

        self.text = QTextBrowser()

        QScroller.grabGesture(
            self.text.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )
        self.text.setObjectName(
            "reportDetails"
        )
        report_box.addWidget(
            self.text,
            1,
        )

        body.addLayout(
            report_box,
            3,
        )

        # History
        history_box = QVBoxLayout()

        history_label = QLabel(
            "HISOBOT TARIXI"
        )
        history_label.setObjectName(
            "sectionTitle"
        )
        history_box.addWidget(
            history_label
        )

        history_help = QLabel(
            "Oldingi yopilgan biznes kunlari"
        )
        history_help.setWordWrap(True)
        history_box.addWidget(
            history_help
        )

        self.history_list = QListWidget()
        self.history_list.setObjectName(
            "reportHistory"
        )
        self.history_list.setMinimumWidth(
            300
        )
        self.history_list.setWordWrap(
            True
        )
        self.history_list.setSpacing(4)
        self.history_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        QScroller.grabGesture(
            self.history_list.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        self.history_list.itemClicked.connect(
            self.open_history_item
        )

        history_box.addWidget(
            self.history_list,
            1,
        )

        cancelled_label = QLabel(
            "BEKOR QILINGANLAR"
        )
        cancelled_label.setObjectName(
            "sectionTitle"
        )
        history_box.addWidget(
            cancelled_label
        )

        cancelled_help = QLabel(
            "Tafsilotlar uchun buyurtmani bosing"
        )
        cancelled_help.setWordWrap(True)
        history_box.addWidget(
            cancelled_help
        )

        self.cancelled_list = QListWidget()
        self.cancelled_list.setWordWrap(True)
        self.cancelled_list.setSpacing(4)
        self.cancelled_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        QScroller.grabGesture(
            self.cancelled_list.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        self.cancelled_list.itemClicked.connect(
            self.open_cancelled_order
        )

        history_box.addWidget(
            self.cancelled_list,
            1,
        )

        body.addLayout(
            history_box,
            2,
        )

        root.addLayout(
            body,
            1,
        )

    def load(self, business_date=None):
        try:
            params = [
                f"period={self.period.currentText().lower()}",
            ]

            order_type = self.order_type.currentData()
            if order_type:
                params.append(
                    f"order_type={order_type}"
                )

            if business_date:
                params.append(
                    f"business_date={business_date}"
                )

            suffix = (
                "?"
                + "&".join(params)
            )

            data = self.client.get(
                "/api/admin/reports/daily"
                + suffix
            )

            self.date.setDate(
                QDate.fromString(
                    data["business_date"],
                    "yyyy-MM-dd",
                )
            )

            self.cards["orders"].setText(
                str(
                    data[
                        "total_order_count"
                    ]
                )
            )

            self.cards["paid"].setText(
                str(
                    data[
                        "paid_order_count"
                    ]
                )
            )

            self.cards["amount"].setText(
                format_money(
                    data[
                        "total_paid_amount"
                    ]
                )
            )

            self.cards["delivery"].setText(
                format_money(
                    data[
                        "by_order_type"
                    ][
                        "DELIVERY"
                    ]
                )
            )

            lines = [
                (
                    f"{self.period.currentText().upper()} "
                    f"HISOBOT — "
                    f"{data['business_date']}"
                ),
                "",
                (
                    "Buyurtmalar: "
                    f"{data['total_order_count']}"
                ),
                (
                    "To‘langan: "
                    f"{data['paid_order_count']}"
                    " / "
                    f"{format_money(data['total_paid_amount'])}"
                ),
                (
                    "Choyxonada: "
                    + format_money(
                        data[
                            "by_order_type"
                        ][
                            "CHAYKHANA"
                        ]
                    )
                ),
                (
                    "Yetkazib berish: "
                    + format_money(
                        data[
                            "by_order_type"
                        ][
                            "DELIVERY"
                        ]
                    )
                ),
            ]

            for key, section_title in [
                (
                    "categories",
                    "KATEGORIYALAR",
                ),
                (
                    "products",
                    "MAHSULOTLAR",
                ),
                (
                    "cashiers",
                    "KASSIRLAR",
                ),
                (
                    "delivery_workers",
                    "YETKAZIB BERUVCHILAR",
                ),
            ]:
                lines.extend(
                    [
                        "",
                        section_title,
                        "─" * 28,
                    ]
                )

                rows = data.get(
                    key,
                    [],
                )

                if not rows:
                    lines.append(
                        "Ma’lumot yo‘q"
                    )
                    continue

                for row in rows:
                    line = (
                        f"{row['name']} — "
                        f"{row['order_count']} buyurtma"
                        " / "
                        f"{format_money(row['amount'])}"
                    )

                    if "quantity" in row:
                        line += (
                            " / miqdor: "
                            f"{row['quantity']}"
                        )

                    lines.append(line)

            self.text.setPlainText(
                "\n".join(lines)
            )

        except Exception as error:
            self.on_error(error)

        self.load_history()
        self.load_cancelled(business_date)

    def load_cancelled(self, business_date=None):
        try:
            params = [
                f"period={self.period.currentText().lower()}",
            ]

            order_type = self.order_type.currentData()

            if order_type:
                params.append(
                    f"order_type={order_type}"
                )

            if business_date:
                params.append(
                    f"business_date={business_date}"
                )

            data = self.client.get(
                "/api/admin/reports/cancelled?"
                + "&".join(params)
            )

            self.cancelled_list.clear()

            if not data:
                item = QListWidgetItem(
                    "Bekor qilingan buyurtma yo‘q"
                )
                item.setFlags(
                    Qt.ItemFlag.NoItemFlags
                )
                item.setSizeHint(
                    QSize(0, 58)
                )
                self.cancelled_list.addItem(
                    item
                )
                return

            for order in data:
                kind = (
                    "CHOYXONADA"
                    if order["order_type"] == "CHAYKHANA"
                    else "YETKAZIB BERISH"
                )

                text = (
                    f"#{order['order_number']} · {kind}\n"
                    f"{format_money(order['total_amount'])}"
                )

                if order.get("cancel_reason"):
                    text += (
                        "\nSabab: "
                        + str(order["cancel_reason"])
                    )

                item = QListWidgetItem(text)

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    int(order["id"]),
                )

                item.setSizeHint(
                    QSize(0, 88)
                )

                self.cancelled_list.addItem(
                    item
                )

        except Exception as error:
            self.on_error(error)

    def open_cancelled_order(self, item):
        order_id = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not order_id:
            return

        dialog = CancelledOrderDialog(
            self.client,
            int(order_id),
            self.on_error,
            self,
        )
        dialog.exec()

    def load_history(self):
        try:
            history = self.client.get(
                "/api/admin/reports/history?limit=20"
            )

            self.history_list.clear()

            if not history:
                item = QListWidgetItem(
                    "Hali yopilgan tarixiy hisobot yo‘q"
                )
                item.setFlags(
                    Qt.ItemFlag.NoItemFlags
                )
                item.setSizeHint(
                    QSize(0, 58)
                )
                self.history_list.addItem(
                    item
                )
                return

            for entry in history:
                date_str = str(
                    entry[
                        "business_date"
                    ]
                )

                text = (
                    f"{date_str}\n"
                    f"{entry['paid_order_count']} ta to‘langan"
                    " · "
                    f"{format_money(entry['total_paid_amount'])}"
                )

                item = QListWidgetItem(
                    text
                )

                item.setData(
                    Qt.ItemDataRole.UserRole,
                    entry,
                )

                item.setSizeHint(
                    QSize(0, 66)
                )

                self.history_list.addItem(
                    item
                )

        except Exception as error:
            self.on_error(error)

    def open_history_item(self, item):
        entry = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not entry:
            return

        business_date = str(
            entry[
                "business_date"
            ]
        )

        self.load(
            business_date
        )

