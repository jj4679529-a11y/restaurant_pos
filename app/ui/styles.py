SPACING = 8
BRAND = "#23654b"

APP_STYLESHEET = """
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 15px;
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
    min-height: 50px;
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
    font-size: 23px;
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
    min-height: 52px;
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
    font-size: 15px;
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
    min-height: 48px;
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
    font-size: 15px;
}

QLabel#receiptSecondary {
    color: #68766e;
    font-size: 13px;
}

QLabel#totalLabel {
    color: #193f30;
    padding: 10px 4px;
    font-size: 29px;
    font-weight: 800;
}

/* ---------- ADMIN ---------- */

QWidget#adminSidebar {
    background: #ffffff;
    border-right: 1px solid #e1e5e2;
}

QPushButton[role="admin-navigation"] {
    text-align: left;
    padding-left: 18px;
    min-height: 54px;
    border: none;
    background: transparent;
}

QPushButton[role="admin-navigation"]:checked {
    background: #e7f0ea;
    color: #174a35;
    font-weight: 800;
}

QWidget#summaryCard {
    padding: 4px;
}

/* ---------- LISTS / INPUTS ---------- */

QListWidget {
    background: #ffffff;
    border: 1px solid #e0e4e1;
    border-radius: 9px;
}

QListWidget::item {
    padding: 7px 6px;
    border-bottom: 1px solid #ecefed;
    min-height: 44px;
}

QListWidget::item:selected {
    background: #e5efe9;
    color: #24352e;
}

QLineEdit,
QComboBox,
QDoubleSpinBox,
QSpinBox,
QDateEdit {
    background: #ffffff;
    border: 1px solid #d5ddd8;
    border-radius: 8px;
    min-height: 46px;
    padding: 3px 9px;
}

/* ---------- TITLES ---------- */

QLabel#dialogTitle {
    font-size: 27px;
    font-weight: 800;
    color: #173f2f;
}

QLabel#sectionTitle {
    font-size: 17px;
    font-weight: 800;
    color: #264b3b;
}

QLabel#statusLabel {
    color: #4d5e55;
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
    border: 1px solid #e0e4e1;
    border-radius: 10px;
}
"""
