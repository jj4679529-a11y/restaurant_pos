SPACING = 8
BRAND = "#23654b"

APP_STYLESHEET = """
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    color: #24352e;
}

QMainWindow,
QDialog {
    background: #f5f5f1;
}

/* ---------- BUTTONS ---------- */

QPushButton {
    background: #ffffff;
    color: #24352e;
    border: 1px solid #dfe4df;
    border-radius: 10px;
    min-height: 44px;
    padding: 3px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: #f0f5f1;
    border-color: #a8c1b3;
}

QPushButton:pressed {
    background: #dce9e1;
}

QPushButton:checked {
    background: #23654b;
    color: #ffffff;
    border-color: #23654b;
}

QPushButton[primary="true"],
QPushButton[role="primary"],
QPushButton[role="success"] {
    background: #23654b;
    color: #ffffff;
    border-color: #23654b;
    font-weight: 700;
}

QPushButton[role="secondary"] {
    background: #eef2ef;
}

QPushButton:disabled {
    background: #e9ebe9;
    color: #919791;
    border-color: #e4e6e4;
}

/* ---------- CASHIER HEADER ---------- */

QLabel#cashierBrand {
    font-size: 18px;
    font-weight: 800;
    color: #173d2e;
    padding: 4px 0;
}

QLabel#connectionStatus {
    color: #49675a;
    font-size: 14px;
    font-weight: 600;
}

/* ---------- CATEGORY ---------- */

QPushButton[role="category"] {
    min-height: 46px;
    text-align: left;
    padding-left: 16px;
    border-radius: 9px;
}

QPushButton[role="category"]:checked,
QPushButton[role="category-selected"] {
    background: #23654b;
    color: #ffffff;
    border-color: #23654b;
}

/* ---------- PRODUCT CARDS ---------- */

QToolButton#productCard {
    background: #ffffff;
    border: 1px solid #e1e5e2;
    border-radius: 14px;
    padding: 8px;
    font-size: 14px;
    font-weight: 650;
}

QToolButton#productCard:hover {
    background: #f7faf8;
    border: 1px solid #79a18d;
}

QToolButton#productCard:pressed {
    background: #e5eee8;
}

QToolButton#productCard:disabled {
    color: #929892;
    background: #eceeec;
}

/* ---------- PANELS ---------- */

QWidget#panel,
QWidget#summaryCard {
    background: #ffffff;
    border: 1px solid #e0e4e1;
    border-radius: 12px;
}

QWidget[role="order-card"] {
    background: #ffffff;
    border-radius: 12px;
}

/* ---------- RECEIPT ---------- */

QListWidget#receiptList {
    background: #ffffff;
    border: none;
    padding: 0;
    border-radius: 0;
}

QWidget#receiptCard {
    background: #ffffff;
    border: none;
    border-bottom: 1px solid #e5e8e6;
    border-radius: 0;
    padding: 5px;
    min-height: 42px;
}

QWidget#receiptCard[selected="true"] {
    background: #f2f7f4;
    border-bottom: 1px solid #77a08a;
}

QWidget#receiptCard QLabel {
    background: transparent;
    border: none;
    color: #27372f;
}

QLabel#receiptTitle {
    font-weight: 700;
    font-size: 14px;
}

QLabel#receiptSecondary {
    color: #68766e;
    font-size: 13px;
}

QLabel#totalLabel {
    color: #193f30;
    padding: 10px 4px;
    font-size: 22px;
    font-weight: 800;
}

/* ---------- ADMIN ---------- */

QWidget#adminSidebar {
    background: #ffffff;
    border-right: 1px solid #e5e7e5;
}

QPushButton[role="admin-navigation"] {
    text-align: left;
    padding: 0 16px;
    min-height: 46px;
    border: none;
    border-radius: 10px;
    background: transparent;
    color: #68726d;
    font-size: 14px;
    font-weight: 650;
}

QPushButton[role="admin-navigation"]:hover {
    background: #f3f6f4;
    color: #244b3b;
}

QPushButton[role="admin-navigation"]:checked {
    background: #e7f0ea;
    color: #174a35;
    font-weight: 800;
}

QLabel#pageTitle {
    color: #1d2d26;
    font-size: 22px;
    font-weight: 800;
}

QLabel#dashboardStatus {
    color: #7a8580;
    font-size: 13px;
    font-weight: 550;
}

QWidget#summaryCard {
    background: #ffffff;
    border: 1px solid #e4e8e5;
    border-radius: 14px;
    padding: 5px;
}

QLabel#summaryTitle {
    color: #75817b;
    font-size: 13px;
    font-weight: 650;
}

QLabel#dashboardValue {
    color: #1f332a;
    font-size: 24px;
    font-weight: 800;
}

/* ---------- LISTS / INPUTS ---------- */

QListWidget {
    background: #ffffff;
    border: 1px solid #e4e8e5;
    border-radius: 12px;
    outline: none;
}

QListWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #eef0ee;
    min-height: 44px;
}

QListWidget::item:hover {
    background: #f7f9f7;
}

QListWidget::item:selected {
    background: #e8f1eb;
    color: #183d2d;
}

QLineEdit,
QComboBox,
QDoubleSpinBox,
QSpinBox,
QDateEdit {
    background: #ffffff;
    color: #26372f;
    border: 1px solid #dce2de;
    border-radius: 10px;
    min-height: 42px;
    padding: 4px 11px;
}

QLineEdit:focus,
QComboBox:focus,
QDoubleSpinBox:focus,
QSpinBox:focus,
QDateEdit:focus {
    border: 1px solid #759b88;
    background: #ffffff;
}

/* ---------- TITLES ---------- */

QLabel#dialogTitle {
    font-size: 22px;
    font-weight: 800;
    color: #1f3028;
}

QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 800;
    color: #596760;
    letter-spacing: 1px;
}

QLabel#statusLabel {
    color: #67756e;
    font-weight: 600;
    padding: 5px;
}

/* ---------- SCROLL / SPLITTER ---------- */

QScrollArea,
QScrollArea > QWidget > QWidget {
    border: none;
    background: transparent;
}

QSplitter::handle {
    background: #ecefed;
    width: 4px;
}

/* ---------- REPORT / HISTORY ---------- */

QListWidget#historyList,
QListWidget#reportHistory,
QListWidget#dashboardCatalog,
QListWidget#adminResourceList {
    background: #ffffff;
    border: 1px solid #e4e8e5;
    border-radius: 12px;
    padding: 4px;
}

QListWidget#dashboardCatalog::item {
    min-height: 42px;
    padding: 6px 10px;
}

QListWidget#adminResourceList::item {
    min-height: 46px;
    padding: 8px 12px;
}

/* ---------- ADMIN EDITOR CARDS ---------- */

QWidget#adminFormPanel {
    background: #ffffff;
    border: 1px solid #e4e8e5;
    border-radius: 14px;
}

QWidget#pricePresetCard,
QWidget#addonPriceCard {
    background: #ffffff;
    border: 1px solid #e4e8e5;
    border-radius: 12px;
}

QLabel#pricePresetValue {
    color: #1f332a;
    font-size: 16px;
    font-weight: 800;
}

QLabel#addonPriceName {
    color: #23372e;
    font-size: 16px;
    font-weight: 750;
}

QCheckBox {
    spacing: 10px;
    min-height: 42px;
    font-weight: 650;
}

QCheckBox::indicator {
    width: 24px;
    height: 24px;
}

"""
