SPACING = 8
BRAND = '#23654b'
APP_STYLESHEET = """
QWidget { font-family: Arial, sans-serif; font-size: 16px; color: #253934; }
QMainWindow, QDialog { background: #f3f5f2; }
QPushButton { background: white; color: #253934; border: 1px solid #d4dfd8; border-radius: 8px; min-height: 48px; padding: 2px 8px; font-weight: 500; }
QPushButton:hover { background: #d5e5da; }
QPushButton:checked { background: #23654b; color: white; }
QPushButton:pressed { background: #c9ded0; }
QPushButton[primary="true"] { background: #23654b; color: white; font-weight: 600; }
QPushButton:disabled { background: #e5e8e4; color: #7a837d; border-color: #e0e4df; }
QPushButton[danger="true"] { color: #a34242; }
QToolButton#productCard { background: white; border: 1px solid #d4dfd8; border-radius: 8px; padding: 4px; font-size: 16px; }
QToolButton#productCard:hover { border: 2px solid #23654b; }
QToolButton#productCard:pressed { background: #d5e5da; }
QWidget#panel, QWidget#summaryCard { background: white; border: 1px solid #d4dfd8; border-radius: 6px; }
QListWidget#receiptList { background: #ffffff; border: 1px solid #d4dfd8; padding: 4px; }
QWidget#receiptCard { background: #ffffff; border: 1px solid #dce4de; border-radius: 6px; }
QWidget#receiptCard[selected="true"] { background: #f2f8f3; border: 1px solid #5b9475; }
QWidget#receiptCard QLabel { background: transparent; border: none; color: #253934; }
QLabel#receiptTitle { font-weight: 600; font-size: 16px; }
QLabel#receiptSecondary { color: #66746b; font-size: 14px; }
QScrollArea, QScrollArea > QWidget > QWidget { border: none; background: #f3f5f2; }
QListWidget::item { padding: 4px; border-bottom: 1px solid #e5ebe7; }
QListWidget::item:selected { background: #d5e5da; color: #253934; }
QLabel#dialogTitle { font-size: 26px; font-weight: 700; }
QLabel#sectionTitle { font-size: 19px; font-weight: 700; }
QPushButton[role="primary"], QPushButton[role="success"] { background: #23654b; color: white; font-weight: 700; }
QPushButton[role="secondary"] { background: #e8efeb; }
QPushButton[role="danger"] { color: #a34242; border-color: #a34242; }
QPushButton[role="category"] { padding: 2px 18px; }
QPushButton[role="category"]:checked, QPushButton[role="category-selected"] { background: #23654b; color: white; }
QPushButton[role="admin-navigation"] { text-align: left; padding-left: 12px; }
QWidget[role="order-card"] { background: white; border-radius: 8px; }
QToolButton[role="product-card"]:disabled { color: #7a837d; background: #e5e8e4; }
QLineEdit, QComboBox, QListWidget, QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #cbd5e1; border-radius: 6px; min-height: 42px; padding: 4px 8px; }
QLabel#totalLabel { color: #253934; padding: 8px; font-size: 32px; font-weight: 700; }
QLabel#statusLabel { color: #334155; font-weight: 600; padding: 6px; }
"""
