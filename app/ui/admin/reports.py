from PySide6.QtCore import QDate
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QDateEdit, QPushButton, QTextBrowser, QComboBox, QLabel
from app.ui.state import format_money


class ReportsPage(QWidget):
    def __init__(self, client, on_error, parent=None):
        super().__init__(parent)
        self.client, self.on_error = client, on_error
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat('yyyy-MM-dd')
        self.date.setMinimumHeight(48)
        self.period = QComboBox()
        self.period.addItems(['Kunlik', 'Haftalik', 'Oylik'])
        self.order_type = QComboBox()
        self.order_type.addItem('Umumiy', None)
        self.order_type.addItem('Choyxonada', 'CHAYKHANA')
        self.order_type.addItem('Yetkazib berish', 'DELIVERY')
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel('Davr:'))
        bar.addWidget(self.period)
        bar.addWidget(QLabel('Turi:'))
        bar.addWidget(self.order_type)
        bar.addWidget(self.date)
        load = QPushButton('KUNLIK HISOBOT')
        load.clicked.connect(lambda: self.load(self.date.date().toString('yyyy-MM-dd')))
        bar.addWidget(load)
        today = QPushButton('JORIY BIZNES KUNI')
        today.clicked.connect(lambda: self.load())
        bar.addWidget(today)
        layout.addLayout(bar)
        self.text = QTextBrowser()
        layout.addWidget(self.text)

    def load(self, business_date=None):
        try:
            params = [f'period={self.period.currentText().lower()}', f'order_type={self.order_type.currentData() or ""}']
            if business_date:
                params.append(f'business_date={business_date}')
            suffix = '?' + '&'.join(params)
            data = self.client.get('/api/admin/reports/daily' + suffix)
            self.date.setDate(QDate.fromString(data['business_date'], 'yyyy-MM-dd'))
            lines = [f"{self.period.currentText().upper()} HISOBOT — {data['business_date']}", f"Buyurtmalar: {data['total_order_count']}",
                     f"To‘langan: {data['paid_order_count']} / {format_money(data['total_paid_amount'])}",
                     'Choyxonada: ' + format_money(data['by_order_type']['CHAYKHANA']),
                     'Yetkazib berish: ' + format_money(data['by_order_type']['DELIVERY'])]
            for key, title in [('categories', 'Kategoriyalar'), ('products', 'Mahsulotlar'),
                               ('cashiers', 'Kassirlar'), ('delivery_workers', 'Yetkazib beruvchilar')]:
                lines.extend(['', title])
                lines.extend(f"{r['name']} — {r['order_count']} buyurtma / {format_money(r['amount'])}" +
                             (f" / miqdor: {r['quantity']}" if 'quantity' in r else '') for r in data[key])
            self.text.setPlainText('\n'.join(lines))
        except Exception as error:
            self.on_error(error)
