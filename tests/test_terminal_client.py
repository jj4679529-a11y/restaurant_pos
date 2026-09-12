import json
import os
from pathlib import Path
import subprocess
import sys
from decimal import Decimal

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QMessageBox

from app.ui.api_client import HttpResponse, PosApiClient
from app.ui.checkout import pay_and_print
from app.ui.config import UiSettings
from app.ui.main_window import PosMainWindow
from app.ui.state import CartItem, SessionState
from tests.test_ui_final_menu import qt_app


def test_client_imports_without_database_and_windows_timezone_data():
    code = '''
import sys
from zoneinfo import ZoneInfo, reset_tzpath
class BlockBackend:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('app.database', 'app.core', 'sqlalchemy', 'psycopg2')):
            raise AssertionError('Client imported backend dependency: ' + fullname)
sys.meta_path.insert(0, BlockBackend())
import pos
from app.ui.config import UiSettings
settings = UiSettings(_env_file=None)
assert 'DATABASE_URL' not in type(settings).model_fields
reset_tzpath([])
ZoneInfo.clear_cache()
assert ZoneInfo('Asia/Tashkent').key == 'Asia/Tashkent'
'''
    environment = {k: v for k, v in os.environ.items() if k not in {'DATABASE_URL', 'JWT_SECRET_KEY'}}
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1],
                            env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_distinct_terminal_config_routes_prints_and_keeps_paid(tmp_path, monkeypatch):
    monkeypatch.delenv('POS_PRINTER_ID', raising=False)
    monkeypatch.delenv('POS_API_BASE_URL', raising=False)
    # These are isolated test .env files, not the project's real configuration.
    for index in (1, 2):
        path = tmp_path / f'terminal-{index}.env'
        path.write_text(f'POS_API_BASE_URL=http://terminal-server.test:8000\nPOS_PRINTER_ID={index}\n')
        settings = UiSettings(_env_file=path)
        calls = []
        def transport(request, timeout):
            calls.append(request)
            body = {'payment_status': 'PAID'} if request.full_url.endswith('/pay') else {'status': 'ERROR'}
            return HttpResponse(200, json.dumps(body).encode())
        client = PosApiClient(settings.POS_API_BASE_URL, transport=transport)
        result = pay_and_print(client, 101, settings.POS_PRINTER_ID)
        assert result.payment['payment_status'] == 'PAID' and not result.printed
        assert json.loads(calls[-1].data)['printer_id'] == index
        assert calls[-1].full_url == settings.POS_API_BASE_URL + '/api/orders/101/print'


def test_ui_outage_reconnect_no_fake_save_and_saved_order_retained(qt_app, monkeypatch):
    online = False
    errors = []
    monkeypatch.setattr(QMessageBox, 'critical', lambda *args: errors.append(args[2]))
    def transport(request, timeout):
        if not online:
            raise OSError('simulated Wi-Fi/server outage')
        return HttpResponse(200, b'[]')
    client = PosApiClient('http://terminal-server.test:8000', transport=transport)
    window = PosMainWindow(client, SessionState('fixture-token', {'name': 'Fixture'}),
                           UiSettings(_env_file=None), lambda: None)
    try:
        qt_app.processEvents()
        window.cart.add(CartItem(1, 'Fixture', Decimal('1'), 15000))
        window._save_order()
        assert errors and window.current_order is None and len(window.cart.items) == 1
        saved = {'id': 101, 'order_number': '00101', 'payment_status': 'PENDING', 'total_amount': 15000}
        window.current_order = saved
        window.reload_catalog()
        assert window.current_order == saved
        assert window.connection_label.text() == 'Server: ulanmagan'
        online = True
        window.reload_catalog()
        assert window.connection_label.text() == 'Server: ulangan'
        assert window.current_order == saved
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
