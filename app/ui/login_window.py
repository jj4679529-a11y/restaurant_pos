from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.api_client import ApiAuthenticationError, ApiConnectionError, ApiError, PosApiClient
from app.ui.state import SessionState


class LoginWindow(QWidget):
    def __init__(self, client: PosApiClient, on_login: Callable[[SessionState], None]) -> None:
        super().__init__()
        self.client = client
        self.on_login = on_login
        self.setWindowTitle("Restaurant POS — Kirish")
        self.setMinimumSize(420, 360)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 42, 42, 42)
        title = QLabel("Restaurant POS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 700;")
        subtitle = QLabel("Kassir tizimiga kirish")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(28)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("Foydalanuvchi nomi")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Parol")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Login:", self.username)
        form.addRow("Parol:", self.password)
        layout.addLayout(form)
        layout.addSpacing(20)
        self.login_button = QPushButton("Kirish")
        self.login_button.setMinimumHeight(58)
        self.login_button.clicked.connect(self._login)
        self.password.returnPressed.connect(self._login)
        layout.addWidget(self.login_button)
        layout.addStretch()

    def _login(self) -> None:
        username = self.username.text().strip()
        password = self.password.text()
        if not username:
            QMessageBox.warning(self, "Kirish", "Loginni kiriting")
            return
        self.login_button.setEnabled(False)
        try:
            response = self.client.login(username, password)
        except ApiConnectionError:
            QMessageBox.critical(self, "Server topilmadi", "Serverga ulanib bo‘lmadi. Backend manzilini tekshiring.")
        except ApiAuthenticationError as error:
            if error.code == "INVALID_CREDENTIALS":
                message = "Login yoki parol noto‘g‘ri."
            else:
                message = "Kirish tokeni qabul qilinmadi. Qayta urinib ko‘ring."
            QMessageBox.warning(self, "Kirish rad etildi", message)
        except ApiError as error:
            if error.code == "USER_INACTIVE":
                message = "Bu foydalanuvchi faol emas. Administratorga murojaat qiling."
            elif error.code == "AUTH_CONFIGURATION_ERROR":
                message = "Server autentifikatsiya uchun sozlanmagan."
            else:
                message = error.message
            QMessageBox.warning(self, "Kirish rad etildi", message)
        else:
            user = response.get("user")
            token = response.get("access_token")
            if not isinstance(user, dict) or not isinstance(token, str):
                QMessageBox.critical(self, "Xato", "Server login javobi noto‘g‘ri.")
                return
            self.on_login(SessionState(access_token=token, user=user))
        finally:
            self.login_button.setEnabled(True)
