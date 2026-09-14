from io import BytesIO
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from PIL import Image
from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox, QMessageBox, QFileDialog
from PySide6.QtCore import QCoreApplication, QEvent
from sqlalchemy import select, func

from app.database.connection import get_db
from app.models import AddOn, Product, PriceOption, ManualPricePreset, Setting, User, UserRole
from app.seed.runner import seed_all
from app.ui.admin.api import AdminApiClient
from app.ui.admin.admin_window import AdminWindow, require_admin, error_message
from app.ui.admin.forms import Editor, RecordEditor
from app.ui.admin.pages import ResourcePage
from app.ui.api_client import HttpResponse, ApiError, ApiAuthenticationError
from app.ui.state import SessionState, CartItem
from tests.auth_helpers import create_test_user
from tests.test_seed import _settings
from tests.test_ui_final_menu import qt_app
from main import app


@pytest.fixture(autouse=True)
def dispose_test_windows(qt_app):
    # Close native widgets deterministically on the GUI thread. TestClient has
    # worker threads; leaving cyclic, parentless dialogs to Python GC is unsafe.
    yield
    windows = list(qt_app.topLevelWidgets())
    for window in windows:
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qt_app.processEvents()


@pytest.fixture
def admin_http(db, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **kw: QMessageBox.StandardButton.Yes)
    username = 'admin-ui-' + uuid4().hex
    admin = create_test_user(db, name='UI Admin', username=username)
    cashier = create_test_user(db, name='UI Cashier', username='cashier-' + uuid4().hex, role=UserRole.CASHIER)
    cashier_name = cashier.username
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as server:
            def transport(request, timeout):
                url = urlsplit(request.full_url)
                response = server.request(request.get_method(), url.path + ('?' + url.query if url.query else ''),
                                          content=request.data, headers=dict(request.header_items()))
                return HttpResponse(response.status_code, response.content)
            client = AdminApiClient('http://testserver', transport=transport)
            auth = client.login(username, 'test-password')
            yield client, auth, cashier_name
    finally:
        app.dependency_overrides.clear()


def fill(editor, data):
    for key, value in data.items():
        widget = editor.widgets[key]
        if isinstance(widget, QComboBox):
            widget.setCurrentIndex(widget.findData(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(value)
        elif isinstance(widget, QSpinBox):
            widget.setValue(value)
        else:
            widget.setText(str(value))


@pytest.mark.parametrize('resource', ['categories', 'products', 'addons', 'workers', 'users', 'printers'])
def test_admin_forms_create_edit_deactivate(db, qt_app, admin_http, resource):
    client, _, _ = admin_http
    name = 'Admin form ' + uuid4().hex[:8]
    if resource == 'products':
        category = client.save_record('categories', {'name': 'Product category ' + uuid4().hex, 'sort_order': 1, 'is_active': True})
    values = {'name': name}
    if resource in {'products', 'addons'}:
        values.update(base_price=5000, allows_manual_price=False, unit_type='PIECE')
    if resource == 'products':
        values['category_id'] = category['id']
    if resource == 'workers':
        values['phone'] = 'test-' + uuid4().hex[:8]
    if resource == 'users':
        values.update(username='user-' + uuid4().hex, role='CASHIER', password='original-test-password')
    if resource == 'printers':
        values.update(terminal_name='TEST', connection_type='NETWORK', address='fixture.invalid:9100')
    errors = []
    editor = RecordEditor(resource, client, None, errors.append)
    fill(editor, values)
    editor.save()
    assert not errors, errors
    assert editor.saved
    record = next(r for r in client.list_records(resource) if r['name'] == name)
    update = RecordEditor(resource, client, record, errors.append)
    fill(update, {'name': name + ' edited', 'is_active': False})
    if resource == 'users':
        fill(update, {'role': 'ADMIN', 'password': 'new-test-password'})
    if resource in {'products', 'addons'}:
        fill(update, {'base_price': 6500})
    update.save()
    assert not errors, errors
    changed = next(r for r in client.list_records(resource) if r['id'] == record['id'])
    assert changed['name'] == name + ' edited' and not changed['is_active']
    if resource == 'users':
        assert changed['role'] == 'ADMIN' and 'password_hash' not in changed and 'password' not in changed
        assert update.widgets['password'].text() == ''
        from app.core.security import verify_password
        stored = db.get(User, changed['id'])
        assert verify_password('new-test-password', stored.password_hash)
        assert not verify_password('original-test-password', stored.password_hash)
    if resource in {'products', 'addons'}:
        assert changed['base_price'] == 6500
    editor.close()
    update.close()


@pytest.mark.parametrize('path', ['/api/admin/printers', '/api/admin/manual-price-presets', '/api/admin/settings', '/api/users'])
def test_cashier_denied_admin_endpoints_and_window(qt_app, admin_http, path):
    client, _, cashier = admin_http
    auth = client.login(cashier, 'test-password')
    session = SessionState(auth['access_token'], auth['user'])
    with pytest.raises(PermissionError):
        require_admin(session)
    with pytest.raises(PermissionError):
        AdminWindow(client, session, lambda: None)
    with pytest.raises(ApiError) as error:
        client.get(path)
    assert error.value.status_code == 403


def test_admin_dashboard_and_all_pages(qt_app, admin_http):
    client, auth, _ = admin_http
    window = AdminWindow(client, SessionState(auth['access_token'], auth['user']), lambda: None)
    qt_app.processEvents()
    assert 'Backend: ulangan' in window.pages['dashboard'].summary.text()
    for key in window.pages:
        window.navigate(key)
    window.close()


def test_osh_editor_atomic_two_prices_and_cashier_sees_changes(db, qt_app, admin_http, monkeypatch):
    client, _, cashier_username = admin_http
    seed_all(db, _settings())
    db.flush()
    page = ResourcePage('products', client, lambda error: pytest.fail(str(error)))
    page.load()
    osh = next(p for p in page.records if p['name'] == 'Osh')
    for index in range(page.rows.count()):
        if 'Osh' in page.rows.item(index).text():
            page.rows.setCurrentRow(index)
            break
    def edit_both(dialog):
        assert set(dialog.widgets) == {'half_price', 'full_price'}
        fill(dialog, {'half_price': 18500, 'full_price': 33500})
        dialog.save()
        return dialog.result()
    monkeypatch.setattr(Editor, 'exec', edit_both)
    page.osh_prices()
    product = next(p for p in client.load_catalog()[1] if p['id'] == osh['id'])
    options = [p for p in product['price_options'] if p['is_active']]
    assert {(o['name'], o['price']) for o in options} == {('0.5 porsiya', 18500), ('1 porsiya', 33500)}
    assert not product['allows_manual_price']
    assert all(not o['is_active'] for o in product['price_options'] if o['name'] not in {'0.5 porsiya', '1 porsiya'})
    # A second save updates the same two identities, never duplicates them.
    ids = {o['id'] for o in options}
    client.save_osh_prices(osh['id'], 19000, 34000)
    updated = client.get(f"/api/products/{osh['id']}")
    assert {o['id'] for o in updated['price_options'] if o['is_active']} == ids
    from app.ui.api_client import PosApiClient
    from app.ui.main_window import PosMainWindow
    from app.ui.config import UiSettings
    from app.ui.dialogs.product_dialog import ProductDialog
    cashier_client = PosApiClient('http://testserver', transport=client._transport)
    auth = cashier_client.login(cashier_username, 'test-password')
    assert auth['user']['role'] == 'CASHIER'
    cashier_window = PosMainWindow(cashier_client, SessionState(auth['access_token'], auth['user']), UiSettings(), lambda: None)
    from tests.ui_helpers import wait_for_catalog
    wait_for_catalog(cashier_window, qt_app)
    cashier_product = next(p for p in cashier_window.products if p['id'] == osh['id'])
    picker = ProductDialog(cashier_product, parent=cashier_window)
    picker.options_group.buttons()[0].click()
    assert picker._item().unit_price == 19000
    picker.options_group.buttons()[1].click()
    assert picker._item().unit_price == 34000
    picker.close()
    cashier_window.close()
    page.close()


@pytest.mark.parametrize('target', ['gosht', 'jizz'])
def test_manual_presets_form_crud_sort_and_rules(db, qt_app, admin_http, target):
    client, _, _ = admin_http
    seed_all(db, _settings())
    db.flush()
    resource = 'addons' if target == 'gosht' else 'products'
    name = "Go'sht" if target == 'gosht' else 'Jizz'
    record = next(r for r in client.list_records(resource) if r['name'] == name)
    rule_editor = RecordEditor(resource, client, record, lambda e: pytest.fail(str(e)))
    assert rule_editor.widgets['allows_manual_price'].isChecked()
    assert not rule_editor.widgets['allows_manual_price'].isEnabled()
    field = 'addon_id' if target == 'gosht' else 'product_id'
    errors = []
    editor = RecordEditor('presets', client, None, errors.append)
    fill(editor, {'target': f"{field}:{record['id']}", 'amount': 23456, 'sort_order': 8})
    editor.save()
    assert not errors
    preset = next(r for r in client.list_records('presets') if r['amount'] == 23456 and r[field] == record['id'])
    edit = RecordEditor('presets', client, preset, errors.append)
    fill(edit, {'amount': 24567, 'sort_order': 1, 'is_active': False})
    edit.save()
    assert not errors
    changed = next(r for r in client.list_records('presets') if r['id'] == preset['id'])
    assert changed['amount'] == 24567 and changed['sort_order'] == 1 and not changed['is_active']
    assert db.scalar(select(func.count()).select_from(Product).where(Product.name == "Go'sht")) == 0
    assert db.scalar(select(Product).where(Product.name == 'Jizz')).allows_manual_price
    for dialog in (rule_editor, editor, edit):
        dialog.saved = True
        dialog.close()


def test_image_upload_editor_replace_remove_and_cashier(db, qt_app, admin_http, tmp_path, monkeypatch):
    client, _, _ = admin_http
    from app.core.config import get_settings
    monkeypatch.setenv('PRODUCT_MEDIA_DIR', str(tmp_path / 'media'))
    get_settings.cache_clear()
    category = client.save_record('categories', {'name': 'Image UI ' + uuid4().hex})
    product = client.save_record('products', {'name': 'Image product', 'category_id': category['id'], 'base_price': 7000, 'unit_type': 'PIECE'})
    source = tmp_path / 'sample.png'
    Image.new('RGB', (20, 20), 'red').save(source)
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **kw: (str(source), ''))
    errors = []
    dialog = RecordEditor('products', client, product, errors.append)
    dialog.choose_image()
    reference = dialog.widgets['image_path'].text()
    assert reference.endswith('.jpg') and '/' not in reference
    dialog.save()
    assert not errors
    updated = client.get(f"/api/products/{product['id']}")
    assert updated['image_path'] == reference
    assert client.load_image(reference)
    remove = RecordEditor('products', client, updated, errors.append)
    remove.remove_image()
    remove.save()
    assert client.get(f"/api/products/{product['id']}")['image_path'] is None
    assert (tmp_path / 'media' / reference).exists()  # No unsafe physical deletion.
    dialog.close()
    remove.close()


def test_invalid_image_is_rejected_without_files(admin_http, tmp_path, monkeypatch):
    client, _, _ = admin_http
    from app.core.config import get_settings
    monkeypatch.setenv('PRODUCT_MEDIA_DIR', str(tmp_path / 'media'))
    get_settings.cache_clear()
    with pytest.raises(ApiError) as error:
        client.upload_image(b'not a picture')
    assert error.value.status_code == 422
    assert not (tmp_path / 'media').exists()


def test_addon_link_unlink_preserves_identity(db, admin_http):
    client, _, _ = admin_http
    seed_all(db, _settings())
    db.flush()
    product = next(p for p in client.list_records('products') if p['name'] == 'Osh')
    addon = next(a for a in client.list_records('addons') if a['name'] == 'Qazi')
    client.set_link(product['id'], addon['id'], False)
    assert not next(l for l in client.links(product['id']) if l['addon_id'] == addon['id'])['is_active']
    assert not any(a['id'] == addon['id'] for a in client.get(f"/api/products/{product['id']}")['available_addons'])
    client.set_link(product['id'], addon['id'], True)
    assert len([l for l in client.links(product['id']) if l['addon_id'] == addon['id']]) == 1


def test_safe_settings_and_unsaved_changes(db, qt_app, admin_http, monkeypatch):
    client, _, _ = admin_http
    db.add(Setting(key='test_private_api_token', value='not-for-ui'))
    db.flush()
    assert all(r['key'] in {'restaurant_name', 'business_day_start', 'timezone'} for r in client.list_records('settings'))
    errors = []
    dialog = RecordEditor('settings', client, {'key': 'restaurant_name', 'value': 'old'}, errors.append)
    fill(dialog, {'value': 'Restaurant fixture'})
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **kw: QMessageBox.StandardButton.No)
    assert not dialog.discard()
    dialog.save()
    assert not errors and dialog.saved
    assert next(r for r in client.list_records('settings') if r['key'] == 'restaurant_name')['value'] == 'Restaurant fixture'
    dialog.close()
    with pytest.raises(ApiError) as error:
        client.request('PATCH', '/api/admin/settings/timezone', {'value': 'UTC'})
    assert error.value.status_code == 400


def test_product_editor_rejects_gosht_product(qt_app, admin_http):
    client, _, _ = admin_http
    category = client.save_record('categories', {'name': 'Rule category ' + uuid4().hex})
    with pytest.raises(ValueError, match='faqat'):
        client.save_record('products', {'name': 'Go‘sht', 'category_id': category['id'], 'base_price': 0, 'unit_type': 'AMOUNT'})


@pytest.mark.parametrize('path,data', [
    ('/api/admin/printers', {'name': 'No', 'terminal_name': 'No', 'connection_type': 'USB', 'address': 'No'}),
    ('/api/admin/products/1/osh-prices', {'half_price': 1, 'full_price': 2}),
    ('/api/admin/products/1/addons/1', {'is_active': False}),
])
def test_admin_writes_denied_for_cashier(admin_http, path, data):
    client, _, cashier = admin_http
    client.login(cashier, 'test-password')
    with pytest.raises(ApiError) as error:
        client.request('POST' if path.endswith('/printers') else 'PUT', path, data)
    assert error.value.status_code == 403


def test_image_upload_requires_admin(admin_http):
    client, _, cashier = admin_http
    client.login(cashier, 'test-password')
    with pytest.raises(ApiError) as error:
        client.upload_image(b'not-an-image')
    assert error.value.status_code == 403


def test_osh_invalid_prices_are_atomic(db, admin_http):
    client, _, _ = admin_http
    seed_all(db, _settings())
    db.flush()
    osh = next(p for p in client.list_records('products') if p['name'] == 'Osh')
    before = [(o['id'], o['price'], o['is_active']) for o in osh['price_options']]
    with pytest.raises(ApiError) as error:
        client.save_osh_prices(osh['id'], 0, 50000)
    assert error.value.status_code == 422
    after = client.get(f"/api/products/{osh['id']}")
    assert [(o['id'], o['price'], o['is_active']) for o in after['price_options']] == before


def test_admin_money_keypad_keeps_draft_until_save(qt_app, monkeypatch):
    from unittest.mock import Mock
    from app.ui.dialogs.number_dialog import NumberDialog
    save = Mock()
    monkeypatch.setattr(NumberDialog, 'money', lambda *a, **kw: 18500)
    editor = Editor('Narx', [('half_price', '0.5 porsiya', 'money')], {'half_price': 0}, save, lambda e: pytest.fail(str(e)))
    editor.money_keypad(editor.widgets['half_price'])
    assert editor.values()['half_price'] == 18500
    save.assert_not_called()
    editor.save()
    save.assert_called_once_with({'half_price': 18500})
    editor.close()
