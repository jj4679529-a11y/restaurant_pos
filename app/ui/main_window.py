from collections.abc import Callable
from typing import Any
from decimal import Decimal

from PySide6.QtCore import QTimer, Qt
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
        self.selected_category_id: int | None = None
        self.current_order: dict[str, Any] | None = None
        self.payment_uncertain = False
        self.setWindowTitle("Restaurant POS — Kassir")
        self.setMinimumSize(980, 600)
        self._build()
        self._start_clock()
        # Defer until the launcher owns/shows this window; an expired session
        # during catalog loading can then safely switch back to login.
        QTimer.singleShot(0, self.reload_catalog_async)

    def _build(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)
        root_layout.addLayout(self._top_bar())
        navigation = QHBoxLayout()
        self.fresh_order_button = QPushButton('YANGI BUYURTMA')
        self.fresh_order_button.clicked.connect(self._new_order)
        self.saved_orders_button = QPushButton('SAQLANGAN BUYURTMALAR')
        self.saved_orders_button.clicked.connect(self._saved_orders)
        navigation.addWidget(self.fresh_order_button)
        navigation.addWidget(self.saved_orders_button)
        navigation.addStretch()
        refresh = QPushButton('Menyuni yangilash')
        refresh.clicked.connect(self.reload_catalog_async)
        navigation.addWidget(refresh)
        self.fresh_order_button.setCheckable(True)
        self.fresh_order_button.setChecked(True)
        root_layout.addLayout(navigation)
        root_layout.addLayout(self._order_type_bar())
        self.delivery_container = QWidget()
        delivery_layout = QHBoxLayout(self.delivery_container)
        delivery_layout.setContentsMargins(0, 0, 0, 0)
        delivery_layout.addWidget(QLabel("Yetkazib beruvchi:"))
        self.delivery_worker_combo = QComboBox()
        self.delivery_worker_combo.setMinimumWidth(320)
        delivery_layout.addWidget(self.delivery_worker_combo)
        delivery_layout.addStretch()
        self.delivery_container.setVisible(False)
        root_layout.addWidget(self.delivery_container)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._category_panel())
        splitter.addWidget(self._product_panel())
        self.cart_widget = CartWidget()
        self.cart_widget.remove_button.clicked.connect(self._remove_selected_cart_item)
        self.cart_widget.clear_button.clicked.connect(self._clear_cart)
        self.cart_widget.plus_button.clicked.connect(lambda: self._change_cart_quantity(1))
        self.cart_widget.minus_button.clicked.connect(lambda: self._change_cart_quantity(-1))
        self.cart_widget.edit_button.clicked.connect(self._edit_cart_item)
        splitter.addWidget(self.cart_widget)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([200, 700, 430])
        self.splitter = splitter
        root_layout.addWidget(splitter, 1)

        self.status_label = QLabel("Yangi buyurtma yarating")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.cart_widget.layout().addWidget(self.status_label)
        actions = QVBoxLayout()
        self.save_button = QPushButton("Buyurtmani saqlash")
        self.save_button.setMinimumHeight(52)
        self.save_button.setProperty('primary', True)
        self.save_button.clicked.connect(self._save_order)
        self.checkout_button = QPushButton("Chek chop etish")
        self.checkout_button.setMinimumHeight(52)
        self.checkout_button.setProperty('primary', True)
        self.checkout_button.setEnabled(False)
        self.checkout_button.clicked.connect(self._checkout)
        actions.addWidget(self.save_button)
        actions.addWidget(self.checkout_button)
        self.new_order_button = QPushButton("YANGI BUYURTMA")
        self.new_order_button.clicked.connect(self._reset_after_payment)
        self.new_order_button.setVisible(False)
        actions.addWidget(self.new_order_button)
        self.cart_widget.layout().addLayout(actions)
        self.setCentralWidget(root)
        self._sync_actions()

    def _top_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        title = QLabel("Restaurant POS")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        layout.addStretch()
        self.user_label = QLabel(f"Kassir: {self.session.user.get('name', '')}")
        self.connection_label = QLabel("Server: tekshirilmoqda")
        layout.addWidget(self.connection_label)
        self.clock_label = QLabel()
        self.clock_label.setMinimumWidth(60)
        self.logout_button = QPushButton("Chiqish")
        self.logout_button.clicked.connect(self._logout)
        self.admin_button = QPushButton("Admin")
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
            button.setMinimumHeight(44)
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
        title = QLabel("KATEGORIYALAR")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        self.category_scroll = QScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_content = QWidget()
        self.category_layout = QVBoxLayout(self.category_content)
        self.category_layout.addStretch()
        self.category_scroll.setWidget(self.category_content)
        layout.addWidget(self.category_scroll)
        self.category_scroll.setMinimumWidth(180)
        panel.setMaximumWidth(250)
        return panel

    def _product_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        title = QLabel("MAHSULOTLAR")
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
        self.product_scroll.setWidget(self.product_content)
        layout.addWidget(self.product_scroll)
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
        selected_worker = self.delivery_worker_combo.currentData()
        self.delivery_worker_combo.clear()
        self.delivery_worker_combo.addItem("Yetkazib beruvchini tanlang", None)
        for worker in self.workers:
            if worker.get('is_active', True):
                self.delivery_worker_combo.addItem(str(worker["name"]), int(worker["id"]))
        selected_index = self.delivery_worker_combo.findData(selected_worker)
        if selected_index >= 0:
            self.delivery_worker_combo.setCurrentIndex(selected_index)

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
            configurable = product.get('unit_type') == 'LITER' or product['name'].strip().casefold() == 'osh' or product.get("allows_manual_price") or product.get("available_addons") or any(o.get("is_active", True) for o in product.get("price_options", []))
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
        self.delivery_container.setVisible(order_type == "DELIVERY")

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
        self.delivery_worker_combo.setEnabled(editable)
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
        worker_id = self.delivery_worker_combo.currentData() if self._order_type() == "DELIVERY" else None
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
            state = self.current_order['payment_status']
            self.status_label.setText(f"Buyurtma #{self.current_order['order_number']} — {state}")
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
