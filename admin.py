import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.admin.admin_window import AdminWindow, require_admin, error_message
from app.ui.admin.api import AdminApiClient
from app.ui.config import UiSettings
from app.ui.login_window import LoginWindow
from app.ui.styles import APP_STYLESHEET


class AdminApplication:
    def __init__(self, app):
        self.app = app
        settings = UiSettings()
        self.client = AdminApiClient(settings.POS_API_BASE_URL, timeout_seconds=settings.POS_API_TIMEOUT_SECONDS)
        self.window = None

    def show_login(self):
        previous = self.window
        self.window = LoginWindow(self.client, self.show_admin)
        self.window.setWindowTitle('Restaurant POS — Admin kirish')
        self.window.show()
        if previous:
            previous.close()

    def show_admin(self, session):
        try:
            require_admin(session)
            # Verify against server-side role checks, not just a token/user label.
            self.client.get('/api/users?limit=1')
        except Exception as error:
            self.client.clear_session()
            session.clear()
            self.window.password.clear()
            QMessageBox.warning(self.window, 'Ruxsat yo‘q', error_message(error))
            return
        previous = self.window
        self.window = AdminWindow(self.client, session, self.show_login)
        self.window.showMaximized()
        previous.password.clear()
        previous.close()


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    controller = AdminApplication(app)
    controller.show_login()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
