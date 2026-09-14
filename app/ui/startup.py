"""Desktop startup only: no database imports or credentials."""
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit

from PySide6.QtCore import QLockFile, QStandardPaths
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.api_client import PosApiClient
from app.ui.background import submit
from app.ui.config import PROJECT_ROOT


def can_start_local_server(base_url):
    url = urlsplit(base_url)
    return (url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
            and (url.port or 80) == 8000 and url.path in {"", "/"}
            and not url.username and not url.password)


def health_ready(client):
    try:
        return client.get("/health") == {"status": "ok"}
    except Exception:
        return False


class BackendStarter:
    def __init__(self, settings):
        self.settings = settings
        self.client = PosApiClient(settings.POS_API_BASE_URL, timeout_seconds=1)
        self.process = None

    def ensure_ready(self):
        if health_ready(self.client):
            return
        if not can_start_local_server(self.settings.POS_API_BASE_URL):
            raise RuntimeError("Serverga ulanib bo‘lmadi. Tarmoq va POS_API_BASE_URL manzilini tekshiring.")
        lock_path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)) / "restaurant-pos-start-8000.lock"
        lock = QLockFile(str(lock_path))
        lock.setStaleLockTime(0)
        owns_lock = lock.tryLock(0)
        try:
            if owns_lock and not health_ready(self.client):
                if self.process is None or self.process.poll() is not None:
                    if getattr(sys, "frozen", False):
                        executable = Path(sys.executable).resolve().parent / "RestaurantServer.exe"
                        command = [str(executable)]
                    else:
                        executable = PROJECT_ROOT / "server.py"
                        command = [sys.executable, str(executable)]
                    if not executable.is_file():
                        raise RuntimeError("RestaurantServer topilmadi. Uni POS bilan bir papkaga joylashtiring.")
                    self.process = subprocess.Popen(
                        command, cwd=executable.parent, stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
            deadline = time.monotonic() + self.settings.POS_SERVER_START_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if health_ready(self.client):
                    return
                time.sleep(0.4)
            raise RuntimeError("Server ishga tushmadi. Server .env sozlamalarini tekshiring va qayta urining.")
        finally:
            if owns_lock:
                lock.unlock()


def configure_windows_autostart(enabled, *, registry=None, executable=None):
    if registry is None:
        if sys.platform != "win32":
            return
        import winreg as registry
    if executable is None:
        if not getattr(sys, "frozen", False):
            if enabled:
                raise RuntimeError("Windows avto-start faqat RestaurantPOS.exe uchun mavjud.")
            return
        executable = sys.executable
    # Per-user only: no elevation, scheduled tasks, passwords or machine-wide changes.
    with registry.CreateKey(registry.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            registry.SetValueEx(key, "RestaurantPOS", 0, registry.REG_SZ, f'"{Path(executable)}"')
        else:
            try:
                registry.DeleteValue(key, "RestaurantPOS")
            except FileNotFoundError:
                pass


class StartupWindow(QWidget):
    def __init__(self, settings, ready):
        super().__init__()
        self.starter = BackendStarter(settings)
        self.ready = ready
        self.setWindowTitle("Restaurant POS — Ishga tushirish")
        self.setMinimumSize(520, 240)
        layout = QVBoxLayout(self)
        self.label = QLabel("Server tekshirilmoqda...")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)
        self.retry = QPushButton("Qayta urinish")
        self.retry.clicked.connect(self.start)
        layout.addWidget(self.retry)

    def start(self):
        self.retry.setEnabled(False)
        self.label.setText("Server tekshirilmoqda / ishga tushirilmoqda...")
        self.job = submit(self.starter.ensure_ready, self.completed)

    def completed(self, result, error):
        if not self.isVisible():
            return
        self.retry.setEnabled(True)
        if error:
            self.label.setText(str(error))
        else:
            self.ready()
