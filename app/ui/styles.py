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


/* ---------- CASHIER CLONE ---------- */

QPushButton[role="cashier-tab"] {
    background: transparent;
    color: #66736c;
    border: none;
    border-radius: 8px;
    padding: 4px 14px;
    font-size: 13px;
    font-weight: 750;
}

QPushButton[role="cashier-tab"]:checked {
    background: #ffffff;
    color: #173f2f;
    border: 1px solid #e1e5e2;
}

QPushButton[role="order-type"] {
    background: #ffffff;
    color: #637168;
    border: 1px solid #e0e5e1;
    border-radius: 10px;
    padding: 4px 16px;
    font-weight: 750;
}

QPushButton[role="order-type"]:checked {
    background: #23654b;
    color: #ffffff;
    border-color: #23654b;
}

QToolButton#productCard {
    background: #ffffff;
    border: 1px solid #e5e8e6;
    border-radius: 14px;
    padding: 7px;
    color: #24372e;
    font-size: 14px;
    font-weight: 700;
}

QToolButton#productCard:hover {
    background: #ffffff;
    border: 1px solid #92aa9e;
}

QToolButton#productCard:pressed {
    background: #eef4f0;
}

QWidget[role="order-card"] {
    background: #ffffff;
    border: 1px solid #e4e8e5;
    border-radius: 14px;
}

QListWidget#receiptList {
    background: #ffffff;
    border: none;
    padding: 0;
}

QWidget#receiptCard {
    background: #ffffff;
    border: none;
    border-bottom: 1px solid #eceeec;
    border-radius: 0;
    padding: 3px;
}

QWidget#receiptCard[selected="true"] {
    background: #f4f8f5;
    border-bottom: 1px solid #aac0b4;
}

QLabel#receiptTitle {
    color: #26372f;
    font-size: 14px;
    font-weight: 750;
}

QLabel#receiptSecondary {
    color: #7a847f;
    font-size: 12px;
}

QLabel#totalLabel {
    color: #193f30;
    padding: 12px 4px 8px 4px;
    font-size: 27px;
    font-weight: 850;
}

QLabel#cashierBrand {
    color: #193f30;
    font-size: 19px;
    font-weight: 850;
}

QLabel#connectionStatus {
    color: #718078;
    font-size: 12px;
    font-weight: 650;
}

QPushButton[role="category"] {
    min-height: 48px;
    text-align: left;
    padding-left: 14px;
    background: transparent;
    border: none;
    border-radius: 9px;
    color: #5e6b64;
    font-weight: 700;
}

QPushButton[role="category"]:hover {
    background: #f0f4f1;
}

QPushButton[role="category"]:checked,
QPushButton[role="category-selected"] {
    background: #e6efe9;
    color: #174a35;
    border: none;
    font-weight: 850;
}

QScrollArea {
    background: transparent;
    border: none;
}



/* ==========================================================
   TABLET-FIRST POS
   ========================================================== */

QMainWindow {
    background: transparent;
}

QWidget#cashierRoot {
    background: transparent;
}

/* Main cashier surfaces over photo */
QWidget#cashierRoot QWidget#panel,
QWidget#cashierRoot QWidget#summaryCard {
    background: rgba(255, 251, 241, 238);
    border: 1px solid rgba(206, 172, 91, 190);
    border-radius: 18px;
}

QWidget#cashierRoot QScrollArea,
QWidget#cashierRoot QScrollArea > QWidget > QWidget {
    background: rgba(255, 251, 241, 226);
}

QWidget#cashierRoot QListWidget {
    background: rgba(255, 251, 241, 240);
}

/* Buttons must work by touch, hover is not required */
QPushButton {
    min-height: 56px;
    min-width: 56px;
    padding: 6px 16px;
    font-size: 16px;
    font-weight: 700;
}

QPushButton:hover {
    /* Touch screens have no useful hover state */
    border-color: #d6e2d3;
}

QPushButton:pressed {
    background: #d6a83c;
    color: #12382d;
    border-color: #c49327;
}

QPushButton:checked,
QPushButton[primary="true"],
QPushButton[role="primary"],
QPushButton[role="success"] {
    background: #0b4638;
    color: #fff9ef;
    border: 2px solid #d6a83c;
}

/* Main navigation/category */
QPushButton[role="category"] {
    min-height: 58px;
    font-size: 17px;
    font-weight: 800;
    padding-left: 18px;
}

QPushButton[role="admin-navigation"] {
    min-height: 60px;
    font-size: 17px;
    font-weight: 750;
    padding: 8px 14px;
}

/* Touch-friendly inputs */
QLineEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QDateEdit {
    min-height: 54px;
    font-size: 18px;
    padding: 5px 12px;
}

QComboBox::drop-down {
    width: 54px;
}

QComboBox::down-arrow {
    width: 18px;
    height: 18px;
}

/* Lists */
QListWidget {
    font-size: 18px;
}

QListWidget::item {
    min-height: 54px;
    padding: 8px 10px;
}

/* Scrollbars must be finger friendly */
QScrollBar:vertical {
    width: 22px;
    background: rgba(245, 240, 226, 190);
    margin: 2px;
    border-radius: 10px;
}

QScrollBar::handle:vertical {
    background: #557d69;
    min-height: 64px;
    border-radius: 10px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    height: 22px;
    background: rgba(245, 240, 226, 190);
    margin: 2px;
    border-radius: 10px;
}

QScrollBar::handle:horizontal {
    background: #557d69;
    min-width: 64px;
    border-radius: 10px;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Splitter should not need precise mouse movement */
QSplitter::handle {
    background: rgba(214, 168, 60, 150);
}

QSplitter::handle:horizontal {
    width: 8px;
}

QSplitter::handle:vertical {
    height: 8px;
}

/* Product cards */
QToolButton#productCard {
    min-height: 190px;
    font-size: 17px;
    font-weight: 800;
    background: rgba(255, 251, 241, 244);
    border: 2px solid rgba(214, 168, 60, 170);
}

QToolButton#productCard:hover {
    background: rgba(255, 251, 241, 244);
    border: 2px solid rgba(214, 168, 60, 170);
}

QToolButton#productCard:pressed {
    background: #ead9ad;
    border: 2px solid #0b4638;
}

/* Dialogs */
QDialog {
    background: #f8f2e6;
}

QLabel#dialogTitle {
    font-size: 30px;
    font-weight: 900;
    color: #0b4638;
}

QLabel#sectionTitle {
    font-size: 22px;
    font-weight: 850;
    color: #0b4638;
}

/* Cart */
QLabel#totalLabel {
    font-size: 34px;
    font-weight: 900;
    color: #0b4638;
}

/* Admin panels */
QWidget#adminSidebar {
    background: #073d32;
}

QWidget#adminSidebar QLabel {
    color: #fff9ef;
}

QWidget#adminSidebar QPushButton {
    background: #0b4638;
    color: #fff9ef;
    border: 1px solid #bd9133;
}

QWidget#adminSidebar QPushButton:checked,
QWidget#adminSidebar QPushButton:pressed {
    background: #d6a83c;
    color: #153a2f;
}

/* Tables */
QTableWidget,
QTableView {
    font-size: 17px;
    gridline-color: #ded7c8;
}

QHeaderView::section {
    min-height: 48px;
    font-size: 17px;
    font-weight: 800;
    padding: 8px;
}




/* ==========================================================
   TABLET PHASE 2
   ========================================================== */

QLabel#savedOrdersTitle {
    font-size: 30px;
    font-weight: 900;
    color: #0B4638;
    padding: 6px 4px 12px 4px;
}

QLabel#quantityValue {
    background: #0B4638;
    color: #FFF9EF;
    border: 2px solid #D6A83C;
    border-radius: 14px;
    font-size: 30px;
    font-weight: 900;
    padding: 6px 14px;
}

QPlainTextEdit#touchDetails {
    font-size: 18px;
    line-height: 1.25;
    background: #FFF9EF;
    border: 1px solid #D8C598;
    border-radius: 12px;
    padding: 10px;
}

/* Finger-sized checkbox */
QCheckBox {
    min-height: 52px;
    spacing: 12px;
    font-size: 17px;
}

QCheckBox::indicator {
    width: 30px;
    height: 30px;
}

/* Radio buttons if any are added later */
QRadioButton {
    min-height: 52px;
    spacing: 12px;
    font-size: 17px;
}

QRadioButton::indicator {
    width: 30px;
    height: 30px;
}

/* Calendar popup */
QCalendarWidget QToolButton {
    min-height: 48px;
    min-width: 48px;
    font-size: 17px;
}

QCalendarWidget QAbstractItemView {
    font-size: 18px;
    selection-background-color: #0B4638;
    selection-color: #FFF9EF;
}

QCalendarWidget QSpinBox {
    min-height: 48px;
}

/* Tabs must not be tiny */
QTabBar::tab {
    min-height: 52px;
    min-width: 130px;
    padding: 6px 16px;
    font-size: 17px;
    font-weight: 750;
}

/* Menu popup / Combo popup */
QComboBox QAbstractItemView {
    min-height: 56px;
    font-size: 18px;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    min-height: 52px;
}

/* Readable status/details */
QPlainTextEdit,
QTextEdit,
QTextBrowser {
    font-size: 17px;
}

/* Prevent tiny toolbuttons inside widgets */
QToolButton {
    min-width: 52px;
    min-height: 52px;
}

/* ========================================================== */



/* ==========================================================
   TABLET PHASE 3 — ADMIN
   ========================================================== */

QWidget#adminSidebar {
    background: #073D32;
}

QWidget#adminSidebar QPushButton {
    min-height: 62px;
    font-size: 17px;
    font-weight: 800;
    text-align: left;
    padding-left: 18px;
}

QWidget#adminSidebar QPushButton:checked {
    background: #D6A83C;
    color: #12382D;
    border: 2px solid #F0D486;
}

/* Admin records/lists */
QListWidget#dashboardCatalog::item,
QListWidget::item {
    min-height: 60px;
    padding: 10px 12px;
}

/* Large editable fields */
QWidget#adminFormPanel QLineEdit,
QWidget#adminFormPanel QComboBox,
QWidget#adminFormPanel QSpinBox {
    min-height: 60px;
    font-size: 18px;
}

/* Make spin controls finger-sized */
QSpinBox::up-button,
QDoubleSpinBox::up-button {
    width: 42px;
    height: 28px;
}

QSpinBox::down-button,
QDoubleSpinBox::down-button {
    width: 42px;
    height: 28px;
}

/* Admin form labels */
QWidget#adminFormPanel QLabel {
    font-size: 17px;
    font-weight: 650;
}

/* Preset cards */
QWidget#pricePresetCard {
    background: #FFF9EF;
    border: 1px solid #D8C598;
    border-radius: 12px;
    min-height: 76px;
}

QLabel#pricePresetValue {
    font-size: 21px;
    font-weight: 850;
    color: #0B4638;
}

/* Tables, should any admin page use them */
QTableView::item,
QTableWidget::item {
    padding: 9px;
}

QTableView QScrollBar:vertical,
QTableWidget QScrollBar:vertical {
    width: 24px;
}

/* Dialog confirmation buttons also finger friendly */
QMessageBox QPushButton {
    min-width: 120px;
    min-height: 58px;
    font-size: 17px;
}

/* ========================================================== */



/* ==========================================================
   TABLET PHASE 4 — RESOURCE / IMAGE
   ========================================================== */

QListWidget#adminResourceList::item {
    min-height: 88px;
    padding: 10px 12px;
    border-bottom: 1px solid #DDD3BF;
}

QListWidget#adminResourceList::item:selected {
    background: #D6A83C;
    color: #12382D;
    border: 2px solid #0B4638;
}

QLabel#adminImagePreview {
    background: #EEE6D5;
    border: 2px solid #D6A83C;
    border-radius: 16px;
    padding: 6px;
}

/* Strong selected state for touch */
QListWidget::item:selected {
    background: #D8B451;
    color: #102F27;
    border: 2px solid #0B4638;
}

/* Big buttons in admin dialogs */
QDialog QPushButton {
    min-height: 58px;
}

/* Finger-friendly file/image action buttons */
QWidget#adminFormPanel QPushButton {
    min-height: 60px;
    font-size: 17px;
    font-weight: 750;
}

/* ========================================================== */



/* ==========================================================
   TABLET PHASE 5 — MENU WIZARD / PORTIONS
   ========================================================== */

QLabel#wizardImagePreview {
    background: #EEE6D5;
    border: 2px solid #D6A83C;
    border-radius: 16px;
    padding: 6px;
    font-size: 17px;
    font-weight: 700;
    color: #5D675F;
}

QListWidget#portionsList::item {
    min-height: 76px;
    padding: 10px 14px;
    font-size: 18px;
    font-weight: 700;
    border-bottom: 1px solid #DDD3BF;
}

QListWidget#portionsList::item:selected {
    background: #D6A83C;
    color: #12382D;
    border: 2px solid #0B4638;
}

/* Wizard input controls */
QDialog QLineEdit,
QDialog QComboBox,
QDialog QSpinBox {
    min-height: 60px;
}

/* Wizard buttons */
QDialog QPushButton {
    min-height: 60px;
    font-size: 17px;
    font-weight: 750;
}

/* Make keypad/price buttons very easy to tap */
QPushButton[text="NARX"] {
    min-width: 100px;
}

/* ========================================================== */



/* ==========================================================
   CLEAN RECEIPT — CURRENT ORDER
   ========================================================== */

QWidget[role="order-card"] {
    background: #FFFDF7;
    border: 1px solid #D8CFBA;
    border-radius: 10px;
}

QListWidget#receiptList {
    background: #FFFDF7;
    border: none;
    outline: none;
    padding: 4px 2px;
}

QListWidget#receiptList::item {
    background: transparent;
    border: none;
    padding: 0;
    margin: 0;
}

QWidget#receiptCard {
    background: #FFFDF7;
    border: none;
    border-bottom: 1px solid #D9D1C2;
    border-radius: 0;
}

QLabel#receiptTitle {
    color: #1C2723;
    font-size: 17px;
    font-weight: 800;
}

QLabel#receiptSecondary {
    color: #505952;
    font-size: 15px;
    font-weight: 600;
}

QLabel#totalLabel {
    background: #FFFDF7;
    color: #073D32;
    border: none;
    border-top: 2px solid #073D32;
    border-radius: 0;
    padding: 14px 8px 8px 8px;
    font-size: 25px;
    font-weight: 900;
}

/* ========================================================== */



/* ==========================================================
   CASHIER LIGHT OVERRIDE
   Photo background disabled.
   ========================================================== */

QMainWindow {
    background: #F3F0E8;
}

QWidget#cashierRoot {
    background: #F3F0E8;
}

QWidget#cashierRoot QWidget#panel,
QWidget#cashierRoot QWidget#summaryCard {
    background: #FFFFFF;
    border: 1px solid #E0E4E1;
    border-radius: 14px;
}

QWidget#cashierRoot QScrollArea,
QWidget#cashierRoot QScrollArea > QWidget > QWidget {
    background: #FFFFFF;
}

QWidget#cashierRoot QListWidget {
    background: #FFFFFF;
}

QWidget#cashierRoot QToolButton#productCard {
    background: #FFFFFF;
    border: 1px solid #D9DED9;
}

QWidget#cashierRoot QToolButton#productCard:hover {
    background: #FFFFFF;
    border: 1px solid #92AA9E;
}

/* ========================================================== */



/* ==========================================================
   CASHIER COMPACT LAYOUT
   ========================================================== */

/* Top header */
QLabel#cashierBrand {
    font-size: 17px;
    font-weight: 850;
    padding: 0px 2px;
}

QLabel#connectionStatus {
    font-size: 12px;
}

QPushButton#topCompactButton {
    min-height: 38px;
    max-height: 40px;
    min-width: 72px;
    padding: 2px 10px;
    font-size: 13px;
    border-radius: 8px;
}

/* Order type row */
QLabel#orderTypeLabel {
    font-size: 14px;
    font-weight: 750;
    color: #355447;
}

QPushButton[role="order-type"] {
    min-height: 40px;
    max-height: 42px;
    padding: 2px 12px;
    font-size: 14px;
}

/* Categories */
QPushButton[role="category"] {
    min-height: 48px;
    max-height: 54px;
    padding: 3px 10px;
    padding-left: 12px;
    font-size: 16px;
    font-weight: 750;
}

/* Menu panel heading */
QLabel#sectionTitle {
    font-size: 18px;
    padding: 2px 0px;
}

/* Current order header */
QLabel#currentOrderTitle {
    color: #0B4638;
    font-size: 17px;
    font-weight: 850;
    padding: 2px 0px;
}

QPushButton#cartClearButton {
    background: #FFF9EF;
    color: #7B332E;
    border: 1px solid #D9B7AA;
    border-radius: 7px;
    min-height: 34px;
    max-height: 36px;
    min-width: 82px;
    max-width: 100px;
    padding: 1px 8px;
    font-size: 12px;
    font-weight: 800;
}

QPushButton#cartClearButton:pressed {
    background: #E8D0C7;
    color: #652A26;
    border-color: #B98272;
}

/* Receipt gets maximum vertical room */
QListWidget#receiptList {
    padding: 2px;
}

QWidget#receiptCard {
    padding: 1px;
}

QLabel#receiptTitle {
    font-size: 15px;
    font-weight: 800;
}

QLabel#receiptSecondary {
    font-size: 13px;
}

/* Total compact but strong */
QLabel#totalLabel {
    min-height: 40px;
    max-height: 48px;
    font-size: 22px;
    font-weight: 900;
    padding: 5px 6px;
}

/* Checkout actions are compact */
QPushButton#saveOrderButton,
QPushButton#checkoutButton,
QPushButton#newOrderButton {
    min-height: 40px;
    max-height: 44px;
    padding: 2px 10px;
    font-size: 14px;
    font-weight: 850;
}

/* ========================================================== */



/* ==========================================================
   COMPACT DELIVERY WORKER
   ========================================================== */

QPushButton#deliveryWorkerSummary {
    min-height: 38px;
    max-height: 42px;
    padding: 2px 12px;
    background: #EDF4EF;
    color: #0B4638;
    border: 1px solid #9FB9AA;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 800;
}

QPushButton#deliveryWorkerSummary:pressed {
    background: #DCE9E1;
    border-color: #557D69;
}

/* ========================================================== */

"""
