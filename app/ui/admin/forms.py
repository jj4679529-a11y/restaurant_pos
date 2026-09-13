"""Roomy reusable forms. Drafts never write until Save (uploads are staged assets)."""
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QSpinBox, QCheckBox, QComboBox, QPushButton, QMessageBox, QScrollArea, QWidget, QLabel, QFileDialog

from app.ui.admin.api import menu_name
from app.ui.widgets.product_card import product_pixmap
from app.ui.dialogs.number_dialog import NumberDialog

UNITS = [('Porsiya', 'PORTION'), ('Dona', 'PIECE'), ('Litr', 'LITER'), ('Qo‘lda narx', 'AMOUNT')]


class Editor(QDialog):
    def __init__(self, title, fields, values, save, on_error, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(740, 640)
        self.save_callback, self.on_error = save, on_error
        self.widgets = {}
        self.field_rows = {}
        self.saved = False
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setStyleSheet('background: #f3f5f2;')
        self.form = QFormLayout(content)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setSpacing(12)
        for key, label, kind in fields:
            self.field_rows[key] = self.form.rowCount()
            value = values.get(key)
            if isinstance(kind, list):
                widget = QComboBox()
                for name, data in kind:
                    widget.addItem(name, data)
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
            elif kind == 'bool':
                widget = QCheckBox('Faol / Ha')
                widget.setChecked(bool(value if value is not None else True))
                widget.setMinimumHeight(48)
            elif kind in {'money', 'int'}:
                widget = QSpinBox()
                widget.setRange(0 if kind == 'money' else -2_147_483_647, 2_147_483_647)
                widget.setValue(int(value or 0))
                widget.setMinimumHeight(48)
                if kind == 'money':
                    widget.setSuffix(' so‘m')
            else:
                widget = QLineEdit(str(value or ''))
                if kind == 'password':
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
                    widget.setPlaceholderText('Faqat yangi parol; bo‘sh bo‘lsa o‘zgarmaydi')
                if kind == 'readonly':
                    widget.setReadOnly(True)
            widget.setObjectName(key)
            self.widgets[key] = widget
            if kind == 'money':
                row = QHBoxLayout()
                row.addWidget(widget, 1)
                keypad = QPushButton('RAQAMLAR')
                keypad.clicked.connect(lambda _=False, field=widget: self.money_keypad(field))
                row.addWidget(keypad)
                self.form.addRow(label, row)
            else:
                self.form.addRow(label, widget)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QHBoxLayout()
        cancel = QPushButton('BEKOR QILISH')
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton('SAQLASH')
        self.save_button.setProperty('primary', True)
        self.save_button.clicked.connect(self.save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)
        self.initial = self.values()

    def money_keypad(self, field):
        if not field.isEnabled():
            return
        amount = NumberDialog.money(self, 'Narx', initial=field.value())
        if amount is not None:
            field.setValue(amount)

    def values(self):
        result = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, QComboBox):
                result[key] = widget.currentData()
            elif isinstance(widget, QCheckBox):
                result[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                result[key] = widget.value()
            else:
                result[key] = widget.text() if key == 'password' else widget.text().strip()
        return result

    def discard(self):
        if self.saved or self.values() == self.initial:
            return True
        return QMessageBox.question(self, 'Saqlanmagan o‘zgarishlar', 'O‘zgarishlarni saqlamasdan chiqasizmi?',
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def reject(self):
        if self.discard():
            if 'password' in self.widgets:
                self.widgets['password'].clear()
            super().reject()

    def closeEvent(self, event):
        if self.discard():
            if 'password' in self.widgets:
                self.widgets['password'].clear()
            event.accept()
        else:
            event.ignore()

    def save(self):
        data = self.values()
        if self.initial.get('is_active') and data.get('is_active') is False:
            if QMessageBox.question(self, 'Tasdiqlash', 'Yozuvni nofaol qilasizmi?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
        self.save_button.setEnabled(False)
        try:
            self.save_callback(data)
        except Exception as error:
            self.on_error(error)
        else:
            self.saved = True
            if 'password' in self.widgets:
                self.widgets['password'].clear()
            self.accept()
        finally:
            self.save_button.setEnabled(True)


def fields_for(resource, client, original):
    active = [('is_active', 'Faollik', 'bool')]
    named = [('name', 'Nomi', 'text')]
    if resource == 'categories':
        return named + [('sort_order', 'Tartibi', 'int')] + active
    if resource in {'products', 'addons'}:
        fields = named + [('unit_type', 'Sotish turi', UNITS), ('base_price', 'Narxi', 'money'),
                          ('allows_manual_price', 'Narxni kassir kiritadi', 'bool')] + active
        if resource == 'products':
            categories = [(c['name'], c['id']) for c in client.list_records('categories')]
            fields.insert(1, ('category_id', 'Kategoriya', categories))
            fields.append(('image_path', 'Rasm', 'readonly'))
        return fields
    if resource == 'workers':
        return named + [('phone', 'Telefon', 'text')] + active
    if resource == 'users':
        return named + [('username', 'Login', 'text'), ('role', 'Rol', [('Kassir', 'CASHIER'), ('Administrator', 'ADMIN')]),
                        ('password', 'Yangi parol', 'password')] + (active if original else [])
    if resource == 'printers':
        return named + [('terminal_name', 'Terminal', 'text'), ('connection_type', 'Ulanish', [('USB', 'USB'), ('Tarmoq', 'NETWORK')]),
                        ('address', 'Manzil / device', 'text')] + active
    if resource == 'presets':
        targets = []
        for group in ('products', 'addons'):
            for row in client.list_records(group):
                target_field = 'product_id' if group == 'products' else 'addon_id'
                if row.get('allows_manual_price') or original and original.get(target_field) == row['id']:
                    targets.append((f"{row['name']} · {'Mahsulot' if group == 'products' else 'Qo‘shimcha'}",
                                    f"{'product_id' if group == 'products' else 'addon_id'}:{row['id']}"))
        return [('target', 'Tegishli mahsulot / qo‘shimcha', targets), ('amount', 'Summa', 'money'),
                ('sort_order', 'Tartibi', 'int')] + active
    if resource == 'settings':
        key = original['key']
        kind = [(key_value, key_value)] if (key_value := {'timezone': 'Asia/Tashkent', 'business_day_start': '06:00'}.get(key)) else 'text'
        return [('value', key, kind)]
    raise ValueError(resource)


class RecordEditor(Editor):
    def __init__(self, resource, client, original, on_error, parent=None):
        self.resource, self.client, self.original = resource, client, original
        values = dict(original or {})
        values.setdefault('allows_manual_price', False)
        if resource == 'presets' and original:
            field = 'product_id' if original.get('product_id') else 'addon_id'
            values['target'] = f'{field}:{original[field]}'
        fields = fields_for(resource, client, original)
        super().__init__('Tahrirlash' if original else 'Yangi yozuv', fields, values, self.persist, on_error, parent)
        name = menu_name(values.get('name', ''))
        if resource in {'products', 'addons'} and (name in {'osh', 'jizz', 'gosht', 'qazi'} or name.startswith('tuxum')):
            manual = name in {'jizz', 'gosht'}
            self.widgets['allows_manual_price'].setChecked(manual)
            self.widgets['allows_manual_price'].setEnabled(False)
            if name in {'osh', 'jizz', 'gosht'}:
                self.widgets['base_price'].setValue(0)
                self.widgets['base_price'].setEnabled(False)
                self.widgets['name'].setReadOnly(True)
            unit = 'PORTION' if name == 'osh' else 'AMOUNT' if manual else 'PIECE'
            self.widgets['unit_type'].setCurrentIndex(self.widgets['unit_type'].findData(unit))
            self.widgets['unit_type'].setEnabled(False)
        if resource == 'presets' and original:
            self.widgets['target'].setEnabled(False)
        if resource == 'products':
            self.form.setRowVisible(self.field_rows['image_path'], False)
            self.preview = QLabel()
            self.form.addRow(self.preview)
            self.image_preview()
            actions = QHBoxLayout()
            for label, handler in [('RASM TANLASH / ALMASHTIRISH', self.choose_image), ('RASMNI O‘CHIRISH', self.remove_image)]:
                button = QPushButton(label)
                button.clicked.connect(handler)
                actions.addWidget(button)
            self.form.addRow(actions)
        if resource in {'products', 'addons'}:
            def price_label():
                label = self.form.itemAt(self.field_rows['base_price'], QFormLayout.ItemRole.LabelRole).widget()
                label.setText('1 litr narxi' if self.widgets['unit_type'].currentData() == 'LITER' else 'Narxi')
            self.widgets['unit_type'].currentIndexChanged.connect(price_label)
            price_label()
            if name in {'osh', 'jizz', 'gosht', 'qazi'} or name.startswith('tuxum'):
                self.form.setRowVisible(self.field_rows['unit_type'], False)
                self.form.setRowVisible(self.field_rows['allows_manual_price'], False)
            if name in {'osh', 'jizz', 'gosht'}:
                self.form.setRowVisible(self.field_rows['base_price'], False)
                self.form.addRow(QLabel('Porsiya narxlari — Osh sozlamalarida' if name == 'osh' else 'Narxni kassir kiritadi. Tezkor narxlarni alohida sozlang.'))
            elif name != 'qazi' and not name.startswith('tuxum'):
                def reveal_manual():
                    self.form.setRowVisible(self.field_rows['allows_manual_price'],
                                            self.widgets['unit_type'].currentData() == 'AMOUNT' or self.widgets['allows_manual_price'].isChecked())
                self.widgets['unit_type'].currentIndexChanged.connect(reveal_manual)
                reveal_manual()
        self.initial = self.values()

    def image_preview(self):
        reference = self.widgets['image_path'].text()
        self.preview.setPixmap(product_pixmap(self.client.load_image(reference)))

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Mahsulot rasmi', '', 'Rasmlar (*.png *.jpg *.jpeg *.webp)')
        if not path:
            return
        try:
            if Path(path).stat().st_size > 5 * 1024 * 1024:
                raise ValueError('Rasm hajmi 5 MB dan oshmasin')
            data = Path(path).read_bytes()
            if QImage.fromData(data).isNull():
                raise ValueError('Rasm formati noto‘g‘ri')
            reference = self.client.upload_image(data)
            self.widgets['image_path'].setText(reference)
            self.image_preview()
        except Exception as error:
            self.on_error(error)

    def remove_image(self):
        self.widgets['image_path'].clear()
        self.image_preview()

    def persist(self, data):
        if self.resource in {'categories', 'products', 'addons', 'workers', 'users', 'printers'} and not data.get('name', '').strip():
            raise ValueError('Nomini kiriting')
        if self.resource == 'products':
            data['image_path'] = data['image_path'] or None
        if self.resource == 'presets':
            target = data.pop('target')
            if not target:
                raise ValueError('Avval qo‘lda narxli mahsulot yoki qo‘shimchani sozlang')
            if not self.original:
                field, id = target.split(':')
                data[field] = int(id)
        if self.resource == 'users' and self.original and not data.get('password'):
            data.pop('password', None)
        self.client.save_record(self.resource, data, self.original)
