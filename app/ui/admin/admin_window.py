from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QStackedWidget, QMessageBox, QDialog

from app.ui.api_client import ApiAuthenticationError, ApiConnectionError, ApiError
from app.ui.admin.pages import Dashboard, ResourcePage, TITLES
from app.ui.admin.menu_settings import OshPage


def require_admin(session):
    if session.user.get('role') != 'ADMIN':
        raise PermissionError('Ruxsat yo‘q. Faqat administrator uchun.')


def error_message(error):
    if isinstance(error, ApiConnectionError):
        return 'Serverga ulanib bo‘lmadi. Manzil va ulanishni tekshiring.'
    if isinstance(error, ApiError):
        return {401: 'Sessiya tugadi. Qayta kiring.', 403: 'Ruxsat yo‘q.',
                409: 'Saqlanmadi: yozuv yoki amal bilan ziddiyat bor. Qiymatlarni tekshiring.',
                422: 'Qiymatlarni tekshiring: majburiy maydon, narx yoki format noto‘g‘ri.',
                413: 'Rasm hajmi 5 MB dan oshmasin.'}.get(error.status_code, 'Server amalni bajarmadi: ' + error.message)
    return str(error)


class AdminWindow(QMainWindow):
    def __init__(self, client, session, on_logout, embedded=False):
        super().__init__()
        # Initialize the Qt base even on a rejected constructor path; leaving
        # a half-initialized native QWidget can crash subsequent event processing.
        require_admin(session)
        self.client, self.session, self.on_logout = client, session, on_logout
        self.embedded = embedded
        self._logged_out = False
        self.setWindowTitle('Restaurant POS — Admin')
        self.resize(1366, 768)
        self.setMinimumSize(1024, 700)
        root = QWidget()
        layout = QHBoxLayout(root)
        nav_panel = QWidget()
        nav_panel.setFixedWidth(236)
        nav = QVBoxLayout(nav_panel)
        nav.addWidget(QLabel(f"ADMIN\n{session.user.get('name', '')}"))
        self.stack = QStackedWidget()
        self.pages = {'dashboard': Dashboard(client, self.handle_error, self)}
        self.pages.update({key: ResourcePage(key, client, self.handle_error, self) for key in TITLES})
        self.pages['osh'] = OshPage(client, self.handle_error, self)
        self.pages = {key: self.pages[key] for key in ('dashboard', 'products', 'categories', 'osh', 'addons', 'presets', 'workers', 'users', 'printers', 'settings')}
        self.nav_buttons = {}
        for key, page in self.pages.items():
            button = QPushButton('Osh sozlamalari' if key == 'osh' else 'Dashboard' if key == 'dashboard' else TITLES[key])
            button.setFixedHeight(48)
            button.setCheckable(True)
            button.setProperty('role', 'admin-navigation')
            self.nav_buttons[key] = button
            button.clicked.connect(lambda _=False, value=key: self.navigate(value))
            nav.addWidget(button)
            self.stack.addWidget(page)
        nav.addStretch()
        logout = QPushButton('← Kassaga qaytish' if embedded else 'CHIQISH')
        logout.clicked.connect(self.logout)
        nav.addWidget(logout)
        layout.addWidget(nav_panel)
        layout.addWidget(self.stack, 4)
        self.setCentralWidget(root)
        QTimer.singleShot(0, lambda: self.navigate('dashboard'))

    def navigate(self, key):
        current = self.stack.currentWidget()
        if isinstance(current, OshPage) and not current.can_leave():
            return
        self.stack.setCurrentWidget(self.pages[key])
        for name, button in self.nav_buttons.items():
            button.setChecked(name == key)
        self.pages[key].load()

    def handle_error(self, error):
        QMessageBox.warning(self, 'Admin', error_message(error))
        if isinstance(error, ApiAuthenticationError) or isinstance(error, ApiError) and error.status_code == 403:
            # Force-close protected forms on expired/revoked authorization.
            for dialog in self.findChildren(QDialog):
                if 'password' in getattr(dialog, 'widgets', {}):
                    dialog.widgets['password'].clear()
                dialog.done(0)
            self.logout(force=True)

    def logout(self, _checked=False, *, force=False):
        if self._logged_out:
            return
        current = self.stack.currentWidget()
        if not force and isinstance(current, OshPage) and not current.can_leave():
            return
        self._logged_out = True
        self.client.clear_session()
        self.session.clear()
        self.on_logout()
        self.close()

    def closeEvent(self, event):
        if self.embedded and not self._logged_out:
            self.logout()
            if not self._logged_out:
                event.ignore()
                return
        event.accept()
