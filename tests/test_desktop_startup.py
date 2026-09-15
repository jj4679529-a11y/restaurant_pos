from unittest.mock import MagicMock, Mock

import pytest
from PySide6.QtTest import QTest

from app.ui.api_client import ApiError, ApiConnectionError
from app.ui.config import UiSettings
from app.ui.dialogs.admin_login import authenticate_admin
from app.ui.main_window import PosMainWindow
from app.ui.startup import BackendStarter, can_start_local_server, configure_windows_autostart
from app.ui.state import SessionState
from tests.test_ui_final_menu import qt_app


@pytest.mark.parametrize('url,expected', [
    ('http://127.0.0.1:8000', True), ('http://localhost:8000/', True),
    ('http://[::1]:8000', True), ('http://192.168.1.10:8000', False),
    ('https://localhost:8000', False), ('http://localhost:9000', False),
    ('http://localhost:8000/other', False),
])
def test_local_server_detection(url, expected):
    assert can_start_local_server(url) is expected


@pytest.mark.parametrize('value,expected', [('true', True), ('false', False)])
def test_windows_autostart_config(value, expected, tmp_path):
    from app.runtime_paths import configuration_file
    application = tmp_path / 'app'
    application.mkdir()
    assert configuration_file(application) == tmp_path / 'config' / '.env'
    (application / '.env').touch()
    assert configuration_file(application) == application / '.env'
    settings = UiSettings(_env_file=None, AUTO_START_WITH_WINDOWS=value)
    assert settings.AUTO_START_WITH_WINDOWS is expected
    assert not hasattr(settings, 'DATABASE_URL')


def test_autostart_registry_is_current_user_and_removable():
    registry = MagicMock()
    configure_windows_autostart(True, registry=registry, executable='RestaurantPOS.exe')
    registry.CreateKey.assert_called_with(registry.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run')
    assert registry.SetValueEx.call_args.args[-1] == '"RestaurantPOS.exe"'
    configure_windows_autostart(False, registry=registry, executable='RestaurantPOS.exe')
    assert registry.DeleteValue.call_args.args[-1] == 'RestaurantPOS'


def test_healthy_server_is_not_started(monkeypatch):
    monkeypatch.setattr('app.ui.startup.health_ready', lambda _: True)
    spawn = Mock()
    monkeypatch.setattr('app.ui.startup.subprocess.Popen', spawn)
    BackendStarter(UiSettings()).ensure_ready()
    spawn.assert_not_called()


def test_remote_server_is_never_started(monkeypatch):
    monkeypatch.setattr('app.ui.startup.health_ready', lambda _: False)
    spawn = Mock()
    monkeypatch.setattr('app.ui.startup.subprocess.Popen', spawn)
    with pytest.raises(RuntimeError, match='Tarmoq'):
        BackendStarter(UiSettings(POS_API_BASE_URL='http://192.168.1.10:8000')).ensure_ready()
    spawn.assert_not_called()


@pytest.mark.parametrize('owns_lock', [True, False])
def test_local_launch_serialization(monkeypatch, qt_app, owns_lock):
    answers = iter([False, False, True] if owns_lock else [False, True])
    monkeypatch.setattr('app.ui.startup.health_ready', lambda _: next(answers))
    lock = Mock()
    lock.tryLock.return_value = owns_lock
    monkeypatch.setattr('app.ui.startup.QLockFile', Mock(return_value=lock))
    spawn = Mock()
    monkeypatch.setattr('app.ui.startup.subprocess.Popen', spawn)
    BackendStarter(UiSettings()).ensure_ready()
    assert spawn.call_count == int(owns_lock)
    assert lock.unlock.call_count == int(owns_lock)


def test_startup_timeout_is_reported(monkeypatch, qt_app):
    monkeypatch.setattr('app.ui.startup.health_ready', lambda _: False)
    lock = Mock()
    lock.tryLock.return_value = False
    monkeypatch.setattr('app.ui.startup.QLockFile', Mock(return_value=lock))
    clock = iter([0, 1000])
    monkeypatch.setattr('app.ui.startup.time.monotonic', lambda: next(clock))
    with pytest.raises(RuntimeError, match='Server ishga tushmadi'):
        BackendStarter(UiSettings()).ensure_ready()


def admin_client(role='ADMIN'):
    client = Mock()
    client.login.return_value = {'access_token': 'test-token', 'user': {'role': role}}
    return client


def test_admin_login_checks_backend_permission():
    client = admin_client()
    session = authenticate_admin(client, 'admin', 'runtime-test-password')
    assert session.user['role'] == 'ADMIN'
    client.get.assert_called_once_with('/api/users?limit=1')


def test_cashier_credentials_cannot_open_admin():
    client = admin_client('CASHIER')
    with pytest.raises(PermissionError):
        authenticate_admin(client, 'cashier', 'runtime-test-password')
    client.clear_session.assert_called_once()
    client.get.assert_not_called()


def test_admin_backend_rejection_clears_temporary_token():
    client = admin_client()
    client.get.side_effect = ApiError(403, 'FORBIDDEN', 'Forbidden')
    with pytest.raises(ApiError):
        authenticate_admin(client, 'admin', 'runtime-test-password')
    client.clear_session.assert_called_once()


def test_catalog_load_selects_first_active_category_and_retry(qt_app):
    client = Mock()
    client.load_catalog.return_value = (
        [{'id': 1, 'name': 'Off', 'is_active': False}, {'id': 2, 'name': 'Non'}],
        [{'id': 3, 'name': 'Non', 'category_id': 2, 'base_price': 5000}], [],
    )
    client.load_image.return_value = None
    window = PosMainWindow(client, SessionState('test-token', {'name': 'Cashier'}), UiSettings(), lambda: None)
    window.show()
    for _ in range(100):
        QTest.qWait(10)
        if window.selected_category_id == 2:
            break
    assert window.selected_category_id == 2
    assert window.product_grid.count() >= 1
    assert not window.catalog_message.isVisible()
    client.load_catalog.side_effect = ApiConnectionError('offline')
    window.reload_catalog_async()
    assert window.catalog_message.text() == 'Yuklanmoqda...'
    for _ in range(100):
        QTest.qWait(10)
        if not window.catalog_loading:
            break
    assert window.catalog_retry.isVisible()
    assert 'yuklab bo‘lmadi' in window.catalog_message.text()
    client.load_catalog.side_effect = None
    window.catalog_retry.click()
    for _ in range(100):
        QTest.qWait(10)
        if not window.catalog_loading:
            break
    assert not window.catalog_retry.isVisible()
    window.close()


def test_admin_return_preserves_cashier_window_and_session(qt_app, monkeypatch):
    import pos
    from PySide6.QtWidgets import QDialog

    controller = pos.PosApplication(qt_app)
    controller.client.set_access_token('cashier-token')
    cashier = Mock()
    cashier.cart = object()
    original_cart = cashier.cart
    controller.window = cashier
    dialog = Mock()
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.session = SessionState('admin-token', {'role': 'ADMIN'})
    monkeypatch.setattr(pos, 'AdminLoginDialog', Mock(return_value=dialog))
    admin_window = Mock()
    monkeypatch.setattr(pos, 'AdminWindow', Mock(return_value=admin_window))
    controller.open_admin()
    assert controller.window is admin_window
    assert controller.client.access_token == 'cashier-token'
    controller.return_to_cashier()
    assert controller.window is cashier
    assert cashier.cart is original_cart
    assert controller.client.access_token == 'cashier-token'
    cashier.reload_catalog_async.assert_called_once()


def test_background_work_does_not_block_gui(qt_app):
    from threading import Event
    from app.ui.background import submit

    entered, release = Event(), Event()
    completed = []

    def slow_operation():
        entered.set()
        release.wait(2)
        return 'ready'

    job = submit(slow_operation, lambda result, error: completed.append((result, error)))
    try:
        for _ in range(100):
            QTest.qWait(5)
            if entered.is_set():
                break
        assert entered.is_set()
        assert completed == []  # GUI event loop returned while the worker waited.
    finally:
        release.set()
    for _ in range(100):
        QTest.qWait(5)
        if completed:
            break
    assert completed == [('ready', None)]
