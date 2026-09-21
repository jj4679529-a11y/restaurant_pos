from collections.abc import Callable
from typing import Any
from decimal import Decimal

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QScroller
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ui.api_client import ApiAuthenticationError, ApiConnectionError, ApiError, PosApiClient
from app.ui.checkout import pay_and_print, print_paid_order
from app.ui.config import UiSettings
from app.ui.state import Cart, CartItem, CartValidationError, SessionState, format_money
from app.ui.widgets.cart_widget import CartWidget
from app.ui.widgets.product_card import ProductCard
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.dialogs.saved_orders import SavedOrdersDialog
from app.ui.background import submit


class PosMainWindow(QMainWindow):
    def __init__(
        self,
        client: PosApiClient,
        session: SessionState,
        settings: UiSettings,
        on_logout: Callable[[], None],
        on_admin: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.client = client
        self.session = session
        self.settings = settings
        self.on_logout = on_logout
        self.on_admin = on_admin
        self.catalog_loading = False
        self.catalog_initialized = False
        self.catalog_images = {}
        self.cart = Cart()
        self.categories: list[dict[str, Any]] = []
        self.products: list[dict[str, Any]] = []
        self.workers: list[dict[str, Any]] = []
        self.selected_delivery_worker_id: int | None = None
        self.delivery_worker_buttons: list[QPushButton] = []
        self.selected_category_id: int | None = None
        self.current_order: dict[str, Any] | None = None
        self.payment_uncertain = False
        self.setWindowTitle("Komronbek Zig'ir oshi — Kassir")
        self.setMinimumSize(980, 600)
        self._build()
        self._start_clock()
        # Defer until the launcher owns/shows this window; an expired session
        # during catalog loading can then safely switch back to login.
        QTimer.singleShot(0, self.reload_catalog_async)
        self._apply_layout_geometry()

    def _build(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 10, 12, 10)
        root_layout.setSpacing(9)

        root_layout.addLayout(self._top_bar())

        controls = QHBoxLayout()
        controls.setSpacing(8)

        self.fresh_order_button = QPushButton("YANGI BUYURTMA")
        self.fresh_order_button.setMinimumHeight(44)
        self.fresh_order_button.setCheckable(True)
        self.fresh_order_button.setProperty("role", "cashier-tab")
        self.fresh_order_button.setChecked(True)
        self.fresh_order_button.clicked.connect(self._new_order)

        self.saved_orders_button = QPushButton("SAQLANGANLAR")
        self.saved_orders_button.setMinimumHeight(44)
        self.saved_orders_button.setProperty("role", "cashier-tab")
        self.saved_orders_button.clicked.connect(self._saved_orders)

        self.chaykhana_button = QPushButton("CHOYXONADA")
        self.delivery_button = QPushButton("YETKAZIB BERISH")

        for button in (
            self.chaykhana_button,
            self.delivery_button,
        ):
            button.setCheckable(True)
            button.setMinimumHeight(46)
            button.setProperty("role", "order-type")

        self.chaykhana_button.setChecked(True)

        order_group = QButtonGroup(self)
        order_group.setExclusive(True)
        order_group.addButton(self.chaykhana_button)
        order_group.addButton(self.delivery_button)

        self.chaykhana_button.clicked.connect(
            lambda: self._set_order_type("CHAYKHANA")
        )
        self.delivery_button.clicked.connect(
            lambda: self._set_order_type("DELIVERY")
        )

        refresh = QPushButton("↻")
        refresh.setMinimumSize(44, 44)
        refresh.setMaximumWidth(52)
        refresh.setToolTip("Menyuni yangilash")
        refresh.setProperty("role", "secondary")
        refresh.clicked.connect(self.reload_catalog_async)

        controls.addWidget(self.fresh_order_button)
        controls.addWidget(self.saved_orders_button)
        controls.addSpacing(16)
        controls.addWidget(self.chaykhana_button)
        controls.addWidget(self.delivery_button)
        controls.addStretch()
        controls.addWidget(refresh)

        root_layout.addLayout(controls)

        self.delivery_container = QWidget()
        delivery_layout = QVBoxLayout(self.delivery_container)
        delivery_layout.setContentsMargins(0, 0, 0, 0)
        delivery_layout.setSpacing(6)

        delivery_label = QLabel("Yetkazib beruvchini tanlang:")
        delivery_label.setObjectName("sectionTitle")
        delivery_layout.addWidget(delivery_label)

        self.delivery_worker_scroll = QScrollArea()
        self.delivery_worker_scroll.setWidgetResizable(True)
        self.delivery_worker_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.delivery_worker_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.delivery_worker_scroll.setMinimumHeight(72)
        self.delivery_worker_scroll.setMaximumHeight(170)

        QScroller.grabGesture(
            self.delivery_worker_scroll.viewport(),
            QScroller.ScrollerGestureType.TouchGesture,
        )

        self.delivery_worker_content = QWidget()
        self.delivery_worker_layout = QGridLayout(
            self.delivery_worker_content
        )
        self.delivery_worker_layout.setContentsMargins(0, 0, 0, 0)
        self.delivery_worker_layout.setHorizontalSpacing(8)
        self.delivery_worker_layout.setVerticalSpacing(8)

        self.delivery_worker_scroll.setWidget(
            self.delivery_worker_content
        )

        delivery_layout.addWidget(self.delivery_worker_scroll)

        # Backward-compatible hidden combo.
        # UI da ko‘rinmaydi; eski test/integratsiyalar uchun saqlanadi.
        self.delivery_worker_combo = QComboBox(self)
        self.delivery_worker_combo.hide()
        self.delivery_worker_combo.currentIndexChanged.connect(
            self._delivery_combo_changed
        )

        self.delivery_container.setVisible(False)
        root_layout.addWidget(self.delivery_container)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        category_panel = self._category_panel()
        product_panel = self._product_panel()

        splitter.addWidget(category_panel)
        splitter.addWidget(product_panel)

        self.cart_widget = CartWidget()

        self.cart_widget.remove_button.clicked.connect(
            self._remove_selected_cart_item
        )
        self.cart_widget.clear_button.clicked.connect(
            self._clear_cart
        )
        self.cart_widget.plus_button.clicked.connect(
            lambda: self._change_cart_quantity(1)
        )
        self.cart_widget.minus_button.clicked.connect(
            lambda: self._change_cart_quantity(-1)
        )
        self.cart_widget.edit_button.clicked.connect(
            self._edit_cart_item
        )

        splitter.addWidget(self.cart_widget)

        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(3)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.splitter = splitter
        root_layout.addWidget(splitter, 1)

        self.status_label = QLabel("Yangi buyurtma yarating")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self.cart_widget.layout().addWidget(
            self.status_label
        )

        actions = QVBoxLayout()
        actions.setSpacing(6)

        self.save_button = QPushButton(
            "BUYURTMANI SAQLASH"
        )
        self.save_button.setMinimumHeight(46)
        self.save_button.setProperty(
            "primary",
            True,
        )
        self.save_button.clicked.connect(
            self._save_order
        )

        self.checkout_button = QPushButton(
            "TO‘LASH VA CHEK CHOP ETISH"
        )
        self.checkout_button.setMinimumHeight(46)
        self.checkout_button.setProperty(
            "primary",
            True,
        )
        self.checkout_button.setEnabled(False)
        self.checkout_button.clicked.connect(
            self._checkout
        )

        self.new_order_button = QPushButton(
            "YANGI BUYURTMA"
        )
        self.new_order_button.setMinimumHeight(44)
        self.new_order_button.clicked.connect(
            self._reset_after_payment
        )
        self.new_order_button.setVisible(False)

        actions.addWidget(self.save_button)
        actions.addWidget(self.checkout_button)
        actions.addWidget(self.new_order_button)

        self.cart_widget.layout().addLayout(actions)

        self.setCentralWidget(root)
        self._sync_actions()

    def _apply_layout_geometry(self) -> None:
        self.cart_widget.setMinimumWidth(340)
        self.cart_widget.setMaximumWidth(400)
        self.splitter.setSizes([165, 780, 370])

    def _top_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title = QLabel("KOMRONBEK ZIG'IR OSHI")
        title.setObjectName("cashierBrand")
        layout.addWidget(title)
        layout.addStretch()
        self.user_label = QLabel(f"Kassir: {self.session.user.get('name', '')}")
        self.connection_label = QLabel("Server: tekshirilmoqda")
        self.connection_label.setObjectName("connectionStatus")
        layout.addWidget(self.connection_label)
        self.clock_label = QLabel()
        self.clock_label.setMinimumWidth(60)
        self.logout_button = QPushButton("CHIQISH")
        self.logout_button.setMinimumHeight(48)
        self.logout_button.clicked.connect(self._logout)
        self.admin_button = QPushButton("ADMIN")
        self.admin_button.setMinimumHeight(48)
        self.admin_button.setProperty('role', 'secondary')
        self.admin_button.clicked.connect(lambda: self.on_admin() if self.on_admin else None)
        layout.addWidget(self.admin_button)
        layout.addWidget(self.user_label)
        layout.addWidget(self.clock_label)
        layout.addWidget(self.logout_button)
        return layout

    def _order_type_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        label = QLabel("Buyurtma turi:")
        label.setObjectName("sectionTitle")
        self.chaykhana_button = QPushButton("CHOYXONADA")
        self.delivery_button = QPushButton("YETKAZIB BERISH")
        for button in (self.chaykhana_button, self.delivery_button):
            button.setCheckable(True)
            button.setMinimumHeight(52)
        self.chaykhana_button.setChecked(True)
        group = QButtonGroup(self)
        group.addButton(self.chaykhana_button)
        group.addButton(self.delivery_button)
        self.chaykhana_button.clicked.connect(lambda: self._set_order_type("CHAYKHANA"))
        self.delivery_button.clicked.connect(lambda: self._set_order_type("DELIVERY"))
        layout.addWidget(label)
        layout.addWidget(self.chaykhana_button)
        layout.addWidget(self.delivery_button)
        layout.addStretch()
        return layout

    def _category_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        title = QLabel("KATEGORIYALAR")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.category_scroll = QScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_content = QWidget()
        self.category_layout = QVBoxLayout(self.category_content)
        self.category_layout.addStretch()
        self.category_scroll.setWidget(self.category_content)
        QScroller.grabGesture(self.category_scroll.viewport(), QScroller.ScrollerGestureType.TouchGesture)
        layout.addWidget(self.category_scroll)
        self.category_scroll.setMinimumWidth(150)
        panel.setMinimumWidth(150)
        panel.setMaximumWidth(175)
        return panel

    def _product_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        title = QLabel("MENYU")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.catalog_message = QLabel("Yuklanmoqda...")
        self.catalog_message.setWordWrap(True)
        layout.addWidget(self.catalog_message)
        self.catalog_retry = QPushButton("Qayta urinish")
        self.catalog_retry.clicked.connect(self.reload_catalog_async)
        self.catalog_retry.hide()
        layout.addWidget(self.catalog_retry)
        self.product_scroll = QScrollArea()
        self.product_scroll.setWidgetResizable(True)
        self.product_content = QWidget()
        self.product_grid = QGridLayout(self.product_content)
        self.product_grid.setContentsMargins(4, 4, 4, 4)
        self.product_grid.setHorizontalSpacing(12)
        self.product_grid.setVerticalSpacing(12)
        self.product_scroll.setWidget(self.product_content)
        QScroller.grabGesture(self.product_scroll.viewport(), QScroller.ScrollerGestureType.TouchGesture)
        layout.addWidget(self.product_scroll)
        panel.setMinimumWidth(300)
        return panel

    def _start_clock(self) -> None:
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1_000)
        self._update_clock()

    def _update_clock(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        self.clock_label.setText(datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%H:%M"))

    def _handle_api_error(self, error: Exception, title: str = "Server xatosi") -> None:
        self.connection_label.setText("Server: ulanmagan" if isinstance(error, ApiConnectionError) else "Server: javob berdi")
        if isinstance(error, ApiAuthenticationError):
            QMessageBox.warning(self, "Sessiya tugadi", "Sessiya tugadi. Qayta kiring.")
            self._logout()
        elif isinstance(error, ApiConnectionError):
            QMessageBox.critical(self, "Server topilmadi", "Serverga ulanib bo‘lmadi.")
        elif isinstance(error, ApiError):
            QMessageBox.warning(self, title, error.message)
        else:
            QMessageBox.critical(self, title, str(error))

    def reload_catalog(self) -> None:
        """Synchronous adapter retained for explicit callers; UI uses background jobs."""
        self.connection_label.setText('Menyu yuklanmoqda...')
        try:
            result = self.client.load_catalog()
        except Exception as error:
            self._handle_api_error(error, "Katalog yuklanmadi")
            return
        self._catalog_loaded(result, None)

    def reload_catalog_async(self):
        if self.catalog_loading:
            return
        self.catalog_loading = True
        self.catalog_message.setText("Yuklanmoqda...")
        self.catalog_message.show()
        self.catalog_retry.hide()
        self.product_scroll.setEnabled(False)
        self.connection_label.setText("Menyu yuklanmoqda...")
        self.catalog_job = submit(self._fetch_catalog, self._catalog_loaded)

    def _fetch_catalog(self):
        result = self.client.load_catalog()
        images = {p['id']: self.client.load_image(p.get('image_path')) for p in result[1]}
        return (*result, images)

    def _catalog_loaded(self, result, error):
        self.catalog_loading = False
        if not self.session.access_token:
            return
        self.product_scroll.setEnabled(True)
        if error:
            self.catalog_message.setText("Ma’lumotlarni yuklab bo‘lmadi")
            self.catalog_message.show()
            self.catalog_retry.show()
            self.connection_label.setText("Server: ulanmagan")
            if isinstance(error, ApiAuthenticationError):
                self._handle_api_error(error)
            return
        self.categories, self.products, self.workers = result[:3]
        self.categories = [c for c in self.categories if c.get('is_active', True)]
        # Touch menu order is intentional: all items, Milliy taomlar, then the owner order.
        self.categories.sort(key=lambda c: (0 if str(c['name']).casefold() == 'milliy taomlar' else 1, str(c['name']).casefold()))
        self.catalog_images = result[3] if len(result) > 3 else {}
        if not self.catalog_initialized or self.selected_category_id is not None and self.selected_category_id not in {c['id'] for c in self.categories}:
            self.selected_category_id = self.categories[0]['id'] if self.categories else None
        self.catalog_initialized = True
        self.catalog_retry.hide()
        self._render_categories()
        self.connection_label.setText("Server: ulangan")
        self._render_products()
        active_ids = {
            int(worker["id"])
            for worker in self.workers
            if worker.get("is_active", True)
        }

        if self.selected_delivery_worker_id not in active_ids:
            self.selected_delivery_worker_id = None

        self.delivery_worker_combo.blockSignals(True)
        self.delivery_worker_combo.clear()
        self.delivery_worker_combo.addItem(
            "Yetkazib beruvchini tanlang",
            None,
        )

        for worker in self.workers:
            if worker.get("is_active", True):
                self.delivery_worker_combo.addItem(
                    str(worker["name"]),
                    int(worker["id"]),
                )

        selected_index = self.delivery_worker_combo.findData(
            self.selected_delivery_worker_id
        )
        self.delivery_worker_combo.setCurrentIndex(
            selected_index if selected_index >= 0 else 0
        )
        self.delivery_worker_combo.blockSignals(False)

        self._render_delivery_workers()

    def _render_delivery_workers(self) -> None:
        self._clear_layout(self.delivery_worker_layout)
        self.delivery_worker_buttons = []

        active_workers = [
            worker
            for worker in self.workers
            if worker.get("is_active", True)
        ]

        if not active_workers:
            empty = QLabel("Faol yetkazib beruvchi yo‘q")
            self.delivery_worker_layout.addWidget(empty)
            return

        for worker in active_workers:
            worker_id = int(worker["id"])

            button = QPushButton(str(worker["name"]).upper())
            button.setMinimumHeight(52)
            button.setCheckable(True)
            button.setProperty("role", "category")
            button.setChecked(
                worker_id == self.selected_delivery_worker_id
            )

            button.clicked.connect(
                lambda _checked=False, value=worker_id:
                self._select_delivery_worker(value)
            )

            self.delivery_worker_buttons.append(button)
            self.delivery_worker_layout.addWidget(button)

        self.delivery_worker_layout.addStretch()

    def _delivery_combo_changed(self, _index: int) -> None:
        worker_id = self.delivery_worker_combo.currentData()
        self.selected_delivery_worker_id = (
            int(worker_id)
            if worker_id is not None
            else None
        )
        self._render_delivery_workers()

    def _select_delivery_worker(self, worker_id: int) -> None:
        self.selected_delivery_worker_id = worker_id

        index = self.delivery_worker_combo.findData(worker_id)
        if index >= 0:
            self.delivery_worker_combo.blockSignals(True)
            self.delivery_worker_combo.setCurrentIndex(index)
            self.delivery_worker_combo.blockSignals(False)

        active_workers = [
            worker
            for worker in self.workers
            if worker.get("is_active", True)
        ]

        for button, worker in zip(
            self.delivery_worker_buttons,
            active_workers,
        ):
            button.setChecked(
                int(worker["id"]) == worker_id
            )

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _render_categories(self) -> None:
        self._clear_layout(self.category_layout)
        all_button = QPushButton("BARCHASI")
        all_button.setProperty('role', 'category')
        all_button.setCheckable(True)
        all_button.setChecked(self.selected_category_id is None)
        all_button.clicked.connect(lambda: self._select_category(None))
        self.category_layout.addWidget(all_button)
        for category in self.categories:
            button = QPushButton(str(category["name"]).upper())
            button.setCheckable(True)
            button.setProperty('role', 'category')
            button.setChecked(self.selected_category_id == int(category['id']))
            button.clicked.connect(lambda _checked=False, value=int(category["id"]): self._select_category(value))
            self.category_layout.addWidget(button)
        self.category_layout.addStretch()

    def _select_category(self, category_id: int | None) -> None:
        self.selected_category_id = category_id
        self._render_categories()
        self._render_products()

    def _render_products(self) -> None:
        self._clear_layout(self.product_grid)
        visible = [
            product for product in self.products
            if product.get('is_active', True) and (self.selected_category_id is None or int(product["category_id"]) == self.selected_category_id)
        ]
        columns = max(1, self.product_scroll.viewport().width() // 176)
        if not self.catalog_loading and self.catalog_retry.isHidden():
            self.catalog_message.setText("Bu kategoriyada mahsulot yo‘q" if self.categories else "Katalog bo‘sh. Admin panelda menyuni sozlang.")
            self.catalog_message.setVisible(not visible)
        for index, product in enumerate(visible):
            button = ProductCard(product, self.catalog_images.get(product['id']))
            button.clicked.connect(lambda _checked=False, value=product: self._add_product(value))
            self.product_grid.addWidget(button, index // columns, index % columns)
        self.product_grid.setRowStretch((len(visible) // columns) + 1, 1)

    def _add_product(self, product: dict[str, Any]) -> None:
        if self.current_order is not None:
            QMessageBox.information(self, "Buyurtma saqlangan", "Avval saqlangan buyurtma uchun to‘lovni yakunlang.")
            return
        try:
            configurable = (
                product.get("unit_type") == "LITER"
                or product["name"].strip().casefold() == "osh"
                or "".join(
                    c for c in product["name"].casefold()
                    if c.isalnum()
                ) == "manti"
                or product.get("allows_manual_price")
                or product.get("available_addons")
                or any(
                    option.get("is_active", True)
                    for option in product.get(
                        "price_options",
                        [],
                    )
                )
            )
            item = ProductDialog.choose(product, parent=self) if configurable else CartItem.from_catalog(product, Decimal(1))
            if item is None:
                return
            self.cart.add(item)
        except CartValidationError as error:
            QMessageBox.warning(self, "Narx xatosi", str(error))
            return
        self.cart_widget.render(self.cart)

    def _change_cart_quantity(self, delta):
        if self.current_order is not None:
            return
        row = self.cart_widget.items.currentRow()
        if row >= 0:
            try:
                self.cart.change_quantity(row, delta)
            except CartValidationError as error:
                QMessageBox.warning(self, "Miqdor", str(error))
            self.cart_widget.render(self.cart)
            self.cart_widget.items.setCurrentRow(min(row, len(self.cart.items) - 1))

    def _edit_cart_item(self):
        if self.current_order is not None:
            return
        row = self.cart_widget.items.currentRow()
        if row < 0:
            return
        item = self.cart.items[row]
        product = next(p for p in self.products if p["id"] == item.product_id)
        edited = ProductDialog.choose(product, item, self)
        if edited is not None:
            self.cart.replace(row, edited)
            self.cart_widget.render(self.cart)

    def _set_order_type(self, order_type: str) -> None:
        self.delivery_container.setVisible(
            order_type == "DELIVERY"
        )

        if order_type == "CHAYKHANA":
            self.selected_delivery_worker_id = None
            self._render_delivery_workers()

    def _order_type(self) -> str:
        return "DELIVERY" if self.delivery_button.isChecked() else "CHAYKHANA"

    def _remove_selected_cart_item(self) -> None:
        if self.current_order is not None:
            return
        row = self.cart_widget.items.currentRow()
        if row >= 0:
            self.cart.remove(row)
            self.cart_widget.render(self.cart)

    def _clear_cart(self) -> None:
        if self.current_order is not None:
            return
        self.cart.clear()
        self.cart_widget.render(self.cart)

    def _set_editable(self, editable: bool) -> None:
        for button in (self.cart_widget.minus_button, self.cart_widget.plus_button, self.cart_widget.edit_button):
            button.setEnabled(editable)
        self.save_button.setEnabled(editable)
        self.chaykhana_button.setEnabled(editable)
        self.delivery_button.setEnabled(editable)
        for button in self.delivery_worker_buttons:
            button.setEnabled(editable)
        self.cart_widget.remove_button.setEnabled(editable)
        self.cart_widget.clear_button.setEnabled(editable)
        self.cart_widget.render(self.cart)
        self._sync_actions()

    def _sync_actions(self):
        state = self.current_order.get('payment_status') if self.current_order else 'DRAFT'
        self.save_button.setVisible(state == 'DRAFT')
        self.checkout_button.setVisible(state in {'PENDING', 'PAID'})
        self.checkout_button.setEnabled(state in {'PENDING', 'PAID'})
        self.checkout_button.setText('QAYTA CHOP ETISH' if state == 'PAID' else 'TO‘LASH VA CHEK CHOP ETISH')
        self.new_order_button.setVisible(state == 'PAID')

    def _save_order(self) -> None:
        if self.current_order is not None:
            return
        worker_id = (
            self.selected_delivery_worker_id
            if self._order_type() == "DELIVERY"
            else None
        )
        try:
            payload = self.cart.order_payload(self._order_type(), worker_id)
            self.current_order = self.client.create_order(payload)
        except CartValidationError as error:
            QMessageBox.warning(self, "Buyurtma", str(error))
            return
        except Exception as error:
            self._handle_api_error(error, "Buyurtma saqlanmadi")
            return
        self._set_editable(False)
        self.cart_widget.total_label.setText(f"JAMI: {format_money(self.current_order['total_amount'])}")
        self.checkout_button.setEnabled(self.current_order.get("payment_status") == "PENDING")
        self.status_label.setText(
            f"Buyurtma #{self.current_order['order_number']} saqlandi. To‘lov kutilmoqda."
        )

    def _checkout(self) -> None:
        if self.current_order is None or self.current_order.get("payment_status") not in {"PENDING", "PAID"}:
            QMessageBox.warning(self, "Chek", "Avval PENDING buyurtmani saqlang.")
            return
        self.checkout_button.setEnabled(False)
        try:
            if self.payment_uncertain:
                # A timed-out PAY may already have committed. Read the server
                # state before allowing another payment attempt.
                self.current_order = self.client.get_order(int(self.current_order["id"]))
                self.payment_uncertain = False
                if self.current_order["payment_status"] not in {"PENDING", "PAID"}:
                    self.status_label.setText("Buyurtma holati o‘zgargan. Administratorga murojaat qiling.")
                    return
            if self.current_order["payment_status"] == "PAID":
                outcome = print_paid_order(self.client, int(self.current_order["id"]), self.settings.POS_PRINTER_ID, self.current_order)
            else:
                outcome = pay_and_print(self.client, int(self.current_order["id"]), self.settings.POS_PRINTER_ID)
        except Exception as error:
            if isinstance(error, ApiConnectionError) or isinstance(error, ApiError) and (error.status_code >= 500 or error.code == "INVALID_RESPONSE"):
                self.payment_uncertain = True
                self.status_label.setText("To‘lov natijasi noma’lum. Qayta urinishda server holati tekshiriladi.")
                self.checkout_button.setText("HOLATNI TEKSHIRISH")
            self._handle_api_error(error, "To‘lov bajarilmadi")
            self.checkout_button.setEnabled(True)
            return
        self.current_order["payment_status"] = outcome.payment["payment_status"]
        if outcome.printed:
            message = "To‘lov muvaffaqiyatli. Chek chiqarildi."
        elif not outcome.printer_configured:
            message = "To‘lov saqlandi. Printer sozlanmagan."
        else:
            message = "To‘lov saqlandi. Chek chiqarilmadi."
        QMessageBox.information(self, "To‘lov", message)
        if outcome.printed:
            self._reset_after_payment()
        else:
            self.status_label.setText(f"Buyurtma #{self.current_order['order_number']} — PAID. {message}")
            self.checkout_button.setText("QAYTA CHOP ETISH")
            self.checkout_button.setEnabled(True)
            self.new_order_button.setVisible(True)
        self._sync_actions()

    def _reset_after_payment(self) -> None:
        if self.current_order is not None and self.current_order.get("payment_status") != "PAID":
            return
        self.cart.clear()
        self.cart_widget.render(self.cart)
        self.current_order = None
        self.payment_uncertain = False
        self.checkout_button.setEnabled(False)
        self.checkout_button.setText("Chek chop etish")
        self.new_order_button.setVisible(False)
        self._set_editable(True)
        self.status_label.setText("Yangi buyurtma yarating")

    def _new_order(self):
        if self.current_order is None:
            # Returning to the draft never silently discards an unsaved cart.
            self.status_label.setText('Joriy savat saqlandi. Yangi buyurtmani davom ettiring.')
            return
        # The saved order remains in the backend and can be reopened in history.
        self.current_order = None
        self._reset_after_payment()

    def _saved_orders(self):
        dialog = SavedOrdersDialog(self.client, self.settings.POS_PRINTER_ID, self._handle_api_error, self)
        dialog.exec()
        # History has separate state. Reconcile a saved cart if it was paid there.
        if self.current_order is not None:
            try:
                self.current_order = self.client.get_order(int(self.current_order['id']))
            except Exception as error:
                self._handle_api_error(error)
                return
            state = self.current_order["payment_status"]

            state_name = {
                "PENDING": "KUTILMOQDA",
                "PAID": "TO‘LANGAN",
                "CANCELLED": "BEKOR QILINGAN",
            }.get(state, state)

            self.status_label.setText(
                f"Buyurtma #{self.current_order['order_number']} "
                f"— {state_name}"
            )
            self.checkout_button.setEnabled(state in {'PENDING', 'PAID'})
            self.checkout_button.setText('QAYTA CHOP ETISH' if state == 'PAID' else 'Chek chop etish')
            self._sync_actions()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'product_grid'):
            QTimer.singleShot(0, self._render_products)

    def _logout(self) -> None:
        self.client.clear_session()
        self.session.clear()
        self.on_logout()
        self.close()
