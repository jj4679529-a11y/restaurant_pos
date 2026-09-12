import sys

from PySide6.QtWidgets import QApplication

from app.ui.api_client import PosApiClient
from app.ui.config import UiSettings
from app.ui.login_window import LoginWindow
from app.ui.main_window import PosMainWindow
from app.ui.state import SessionState
from app.ui.styles import APP_STYLESHEET


class PosApplication:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.settings = UiSettings()
        self.client = PosApiClient(
            self.settings.POS_API_BASE_URL,
            timeout_seconds=self.settings.POS_API_TIMEOUT_SECONDS,
        )
        self.window = None

    def show_login(self) -> None:
        self.window = LoginWindow(self.client, self.show_main)
        self.window.show()

    def show_main(self, session: SessionState) -> None:
        previous = self.window
        self.window = PosMainWindow(self.client, session, self.settings, self.show_login)
        self.window.showMaximized()
        if previous is not None:
            previous.close()


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    controller = PosApplication(app)
    controller.show_login()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
