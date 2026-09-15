import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog

from app.ui.api_client import PosApiClient
from app.ui.config import UiSettings
from app.ui.login_window import LoginWindow
from app.ui.main_window import PosMainWindow
from app.ui.state import SessionState
from app.ui.styles import APP_STYLESHEET
from app.ui.startup import StartupWindow, configure_windows_autostart
from app.ui.admin.api import AdminApiClient
from app.ui.admin.admin_window import AdminWindow
from app.ui.dialogs.admin_login import AdminLoginDialog


class PosApplication:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.settings = UiSettings()
        self.client = PosApiClient(
            self.settings.POS_API_BASE_URL,
            timeout_seconds=self.settings.POS_API_TIMEOUT_SECONDS,
        )
        self.window = None
        self.cashier_window = None

    def start(self):
        self.window = StartupWindow(self.settings, self.show_login)
        self.window.show()
        try:
            configure_windows_autostart(self.settings.AUTO_START_WITH_WINDOWS)
        except Exception:
            QMessageBox.warning(self.window, "Windows avto-start", "Avto-start sozlanmadi. Windows ruxsatlarini tekshiring.")
        self.window.start()

    def show_login(self) -> None:
        previous = self.window
        self.window = LoginWindow(self.client, self.show_main)
        self.window.show()
        if previous is not None:
            previous.close()

    def show_main(self, session: SessionState) -> None:
        previous = self.window
        self.window = PosMainWindow(self.client, session, self.settings, self.show_login, self.open_admin)
        self.window.showMaximized()
        if previous is not None:
            previous.close()

    def open_admin(self):
        # Never overwrite the cashier token or charge orders as the admin actor.
        client = AdminApiClient(self.settings.POS_API_BASE_URL, self.settings.POS_API_TIMEOUT_SECONDS)
        dialog = AdminLoginDialog(client, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.cashier_window = self.window
        self.window = AdminWindow(client, dialog.session, self.return_to_cashier, embedded=True)
        self.window.showMaximized()
        self.cashier_window.hide()

    def return_to_cashier(self):
        self.window = self.cashier_window
        self.cashier_window = None
        self.window.showMaximized()
        self.window.reload_catalog_async()


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    try:
        controller = PosApplication(app)
    except Exception:
        QMessageBox.critical(None, "POS sozlamalari", "POS sozlamalari noto‘g‘ri. .env faylini tekshiring.")
        return 1
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
