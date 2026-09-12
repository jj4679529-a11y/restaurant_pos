"""Qt -> centralized HTTP client -> real API/services -> transactional PostgreSQL."""
from collections import Counter
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.database.connection import get_db
from app.models import Order, Payment, PrintJob, Printer, PrinterConnectionType, TelegramOutbox, TelegramMessageType
from app.seed.runner import seed_all
from app.ui.api_client import PosApiClient, HttpResponse
from app.ui.config import UiSettings
from app.ui.state import SessionState
from app.ui.main_window import PosMainWindow
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.dialogs.saved_orders import SavedOrdersDialog, OrderDetailDialog
from main import app
from tests.auth_helpers import create_test_user
from tests.test_seed import _settings
from tests.test_ui_final_menu import qt_app


def test_history_checkout_reprint_with_real_postgresql(db, qt_app):
    seed_all(db, _settings())
    username = f'history-{uuid4().hex}'
    create_test_user(db, name='History test', username=username)
    printer = Printer(name='History fixture', terminal_name='Fixture', connection_type=PrinterConnectionType.USB,
                      address='fixture-only', is_active=True)
    db.add(printer)
    db.flush()
    printer_id = printer.id
    calls = Counter()
    app.dependency_overrides[get_db] = lambda: db
    windows = []
    try:
        with TestClient(app) as server:
            def transport(request, timeout):
                url = urlsplit(request.full_url)
                path = url.path + ('?' + url.query if url.query else '')
                calls[(request.get_method(), url.path)] += 1
                response = server.request(request.get_method(), path, content=request.data, headers=dict(request.header_items()))
                return HttpResponse(response.status_code, response.content)
            client = PosApiClient('http://testserver', transport=transport)
            auth = client.login(username, 'test-password')
            errors = []
            window = PosMainWindow(client, SessionState(auth['access_token'], auth['user']), UiSettings(POS_PRINTER_ID=printer_id), lambda: None)
            windows.append(window)
            qt_app.processEvents()
            product = next(p for p in window.products if p['name'] == 'Osh')
            dialog = ProductDialog(product)
            windows.append(dialog)
            dialog.options_group.buttons()[0].click()
            window.cart.add(dialog._item())
            window.cart_widget.render(window.cart)
            assert calls[('POST', '/api/orders')] == 0
            window.save_button.click()
            assert window.current_order is not None
            order_id = window.current_order['id']
            assert db.get(Order, order_id).payment_status.value == 'PENDING'
            window.fresh_order_button.click()
            assert window.current_order is None and not window.cart.items
            history = SavedOrdersDialog(client, printer_id, errors.append)
            windows.append(history)
            history.filter('PENDING')
            assert any(f'#{window.client.get_order(order_id)["order_number"]}' in history.rows.item(i).text() for i in range(history.rows.count()))
            detail = OrderDetailDialog(client, order_id, printer_id, errors.append)
            windows.append(detail)
            detail.action.click()
            assert detail.order['payment_status'] == 'PAID'
            assert 'Chek chiqarilmadi' in detail.status.text()
            first_jobs = db.scalars(select(PrintJob).where(PrintJob.order_id == order_id)).all()
            assert len(first_jobs) == 1 and first_jobs[0].status.value == 'ERROR'
            first_id = first_jobs[0].id
            reopened = OrderDetailDialog(client, order_id, printer_id, errors.append)
            windows.append(reopened)
            reopened.action.click()
            assert calls[('POST', f'/api/orders/{order_id}/pay')] == 1
            assert calls[('POST', f'/api/orders/{order_id}/print')] == 2
            assert calls[('POST', '/api/orders')] == 1
            assert db.scalar(select(func.count()).select_from(Payment).where(Payment.order_id == order_id)) == 1
            assert db.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.order_id == order_id, TelegramOutbox.message_type == TelegramMessageType.PAID_ORDER)) == 1
            assert db.scalar(select(func.count()).select_from(PrintJob).where(PrintJob.order_id == order_id)) == 2
            assert db.get(PrintJob, first_id).status.value == 'ERROR'
            db.expire_all()
            assert db.get(Order, order_id).payment_status.value == 'PAID'
            assert not errors
    finally:
        for window in reversed(windows):
            window.close()
        app.dependency_overrides.clear()
