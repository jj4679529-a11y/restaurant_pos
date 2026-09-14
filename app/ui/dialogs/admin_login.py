from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from app.ui.admin.admin_window import require_admin, error_message
from app.ui.background import submit
from app.ui.state import SessionState


def authenticate_admin(client, username, password):
    try:
        response = client.login(username, password)
        session = SessionState(response["access_token"], response["user"])
        require_admin(session)
        client.get("/api/users?limit=1")  # Enforced by existing backend permissions.
        return session
    except Exception:
        client.clear_session()
        raise


class AdminLoginDialog(QDialog):
    def __init__(self, client, parent=None):
        super().__init__(parent)
        self.client = client
        self.session = None
        self.busy = False
        self.setWindowTitle("Admin — Kirish")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Login", self.username)
        form.addRow("Parol", self.password)
        layout.addLayout(form)
        self.message = QLabel("Administrator hisobini kiriting")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        self.button = QPushButton("Admin panelga kirish")
        self.button.setProperty("primary", True)
        self.button.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        layout.addWidget(self.button)

    def login(self):
        if self.busy or not self.username.text().strip():
            return
        self.busy = True
        self.button.setEnabled(False)
        username, password = self.username.text().strip(), self.password.text()
        self.password.clear()
        self.job = submit(lambda: authenticate_admin(self.client, username, password), self.completed)

    def completed(self, session, error):
        self.busy = False
        self.button.setEnabled(True)
        self.job.operation = None  # Drop the closure containing runtime credentials.
        if error:
            messages = {
                'INVALID_CREDENTIALS': 'Login yoki parol noto‘g‘ri.',
                'USER_INACTIVE': 'Bu foydalanuvchi faol emas.',
            }
            self.message.setText(messages.get(getattr(error, 'code', None), error_message(error)))
        else:
            self.session = session
            self.accept()

    def reject(self):
        if not self.busy:
            self.password.clear()
            self.client.clear_session()
            super().reject()
