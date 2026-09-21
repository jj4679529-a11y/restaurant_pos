from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models import Product, User, Setting
from app.schemas.catalog import ProductCreate
from app.services.business_day_service import get_current_business_date
from app.services.final_menu_service import prepare_final_menu
from app.ui.api_client import PosApiClient, ApiError
from app.ui.dialogs.product_dialog import ProductDialog
from app.ui.widgets.product_card import ProductCard
from app.ui.state import CartItem, CartValidationError
from tests.test_admin_ui import admin_http, dispose_test_windows
from tests.test_ui_final_menu import qt_app


def category(client):
    return client.save_record('categories', {'name': 'Final ' + uuid4().hex})['id']


def product(client, name, unit='PIECE', price=5000, **extra):
    return client.save_record('products', dict(category_id=category(client), name=name, unit_type=unit,
                                               base_price=price, allows_manual_price=False, **extra))


@pytest.mark.parametrize('name', ['Osh', 'Sho‘rva', 'Ko‘za sho‘rva', 'Mastava', 'Non'])
def test_configurable_portions_and_bread(admin_http, name):
    client, _, _ = admin_http
    item = product(client, name, 'PORTION', 0)
    labels = ['Butun', 'Yarim', 'Chorak'] if name == 'Non' else ['Kichik', 'O‘rta', 'Katta']
    options = []
    for i, label in enumerate(labels):
        options.append(client.post(f'/api/products/{item["id"]}/price-options',
                       {'name': label, 'quantity': str(Decimal(i + 1) / 4), 'price': 5000 * (i + 1)}))
    current = client.get(f'/api/products/{item["id"]}')
    for option in options:
        cart = CartItem.from_catalog(current, Decimal(1), price_option=option)
        order = client.create_order({'order_type': 'CHAYKHANA', 'items': [cart.to_payload()]})
        assert order['total_amount'] == option['price']


@pytest.mark.parametrize('name', ['Manti', 'Choy', 'Novot', 'Kompot', 'Ayron', 'Salat'])
def test_final_piece_products(admin_http, name):
    client, _, _ = admin_http
    item = product(client, name)
    order = client.create_order({'order_type': 'CHAYKHANA', 'items': [{'product_id': item['id'], 'quantity': '2.000'}]})
    assert order['total_amount'] == 10000
    updated = client.save_record('products', {'base_price': 7000}, item)
    assert client.get(f'/api/products/{item["id"]}')['base_price'] == 7000


def test_cashier_phone_login_payment_and_report_attribution(admin_http):
    admin, _, _ = admin_http
    username = 'final-cashier-' + uuid4().hex
    user = admin.save_record('users', {'name': 'Ali', 'phone': '+998901234567', 'username': username,
                                      'password': 'test-password', 'role': 'CASHIER'})
    assert user['phone'] == '+998901234567'
    cashier = PosApiClient('http://testserver', transport=admin._transport)
    assert cashier.login(username, 'test-password')['user']['id'] == user['id']
    worker = admin.save_record('workers', {'name': 'Vali ' + uuid4().hex, 'phone': '123', 'is_active': True})
    item = product(admin, 'Manti')
    # Creator and payer deliberately differ: report must attribute the payer.
    order = admin.create_order({'order_type': 'DELIVERY', 'delivery_worker_id': worker['id'],
                                  'items': [{'product_id': item['id'], 'quantity': '2'}]})
    cashier.pay_order(order['id'])
    report = admin.get('/api/admin/reports/daily')
    assert report['total_order_count'] == report['paid_order_count'] == 1
    assert report['total_paid_amount'] == report['by_order_type']['DELIVERY'] == 10000
    assert report['cashiers'] == [{'id': user['id'], 'name': 'Ali', 'order_count': 1, 'amount': 10000}]
    assert report['delivery_workers'][0]['id'] == worker['id']
    assert report['delivery_workers'][0]['amount'] == report['products'][0]['amount'] == report['categories'][0]['amount'] == 10000
    with pytest.raises(ApiError) as error:
        cashier.pay_order(order['id'])
    assert error.value.status_code == 409


def test_jizz_and_gosht_minimum(admin_http):
    client, _, _ = admin_http
    jizz = product(client, 'Jizz', 'AMOUNT', 0)
    order = client.create_order({'order_type': 'CHAYKHANA', 'items': [{'product_id': jizz['id'], 'quantity': '1', 'manual_price': 15000}]})
    assert order['total_amount'] == 15000
    osh = product(client, 'Osh', 'PORTION', 0)
    option = client.post(f'/api/products/{osh["id"]}/price-options', {'name': 'Maxsus', 'quantity': '0.75', 'price': 15000})
    fixed_addons = []
    for name in ['Tuxum', 'Bedana tuxum', 'Qazi', 'Go‘sht']:
        addon = client.save_record('addons', {'name': name, 'unit_type': 'AMOUNT' if name == 'Go‘sht' else 'PIECE',
                                   'base_price': 0 if name == 'Go‘sht' else 3000, 'allows_manual_price': name == 'Go‘sht'})
        client.set_link(osh['id'], addon['id'], True)
        if name != 'Go‘sht':
            fixed_addons.append({'addon_id': addon['id'], 'quantity': '2'})
    meat = addon
    payload = {'order_type': 'CHAYKHANA', 'items': [{'product_id': osh['id'], 'quantity': '1',
               'selected_price_option_id': option['id'], 'addons': [{'addon_id': meat['id'], 'quantity': '1', 'manual_price': 5000}] + fixed_addons}]}
    assert client.create_order(payload)['total_amount'] == 38000
    payload['items'][0]['addons'][0]['manual_price'] = 4999
    with pytest.raises(ApiError) as error:
        client.create_order(payload)
    assert error.value.code == 'gosht_minimum'


def test_volume_metadata_is_not_sale_quantity(admin_http, qt_app):
    client, _, _ = admin_http
    item = product(client, 'Coca-Cola', price=15000, volume_liters='1.5')
    assert Decimal(client.get(f'/api/products/{item["id"]}')['volume_liters']) == Decimal('1.5')
    assert CartItem.from_catalog(item, Decimal(1)).total_price == 15000
    assert '1.5 L' in ProductCard(item).text()


def test_arbitrary_osh_portion_and_piece_drink_ui(qt_app):
    osh = {'id': 1, 'name': 'Osh', 'base_price': 0, 'price_options': [
        {'id': 9, 'name': 'Maxsus', 'quantity': '0.75', 'price': 24000, 'is_active': True}]}
    dialog = ProductDialog(osh)
    dialog.options_group.buttons()[0].click()
    assert dialog._item().unit_price == 24000
    for name in ['Kompot', 'Ayron']:
        item = {'id': 2, 'name': name, 'base_price': 6000, 'unit_type': 'PIECE'}
        picker = ProductDialog(item)
        assert not picker.is_liter
        assert picker._item().total_price == 6000
        item['unit_type'] = 'LITER'
        with pytest.raises(CartValidationError):
            CartItem.from_catalog(item, Decimal(1))


def test_final_menu_idempotent_preserves_prices(db):
    prepare_final_menu(db)
    product = db.scalar(select(Product).where(Product.name == 'Manti'))
    product.base_price = 12345
    db.flush()
    assert prepare_final_menu(db)['created'] == 0
    assert product.base_price == 12345


def test_configured_business_boundary(db):
    db.add_all([Setting(key='business_day_start', value='04:30'), Setting(key='timezone', value='Asia/Tashkent')])
    db.flush()
    now = datetime(2090, 5, 2, 4, 29, tzinfo=ZoneInfo('Asia/Tashkent'))
    assert get_current_business_date(now, db).isoformat() == '2090-05-01'
    assert get_current_business_date(now.replace(minute=30), db).isoformat() == '2090-05-02'


def test_cancelled_report_lists_only_cancelled_orders_with_filters(admin_http):
    admin, _, _ = admin_http

    item = product(
        admin,
        'Cancelled report item ' + uuid4().hex[:6],
        price=12000,
    )

    worker = admin.save_record(
        'workers',
        {
            'name': 'Cancelled Worker ' + uuid4().hex[:6],
            'phone': '99890' + uuid4().hex[:7],
            'is_active': True,
        },
    )

    # 1) Choyxonada -> PAID -> CANCELLED
    chay = admin.create_order({
        'order_type': 'CHAYKHANA',
        'items': [
            {
                'product_id': item['id'],
                'quantity': '1',
            }
        ],
    })

    admin.pay_order(chay['id'])
    admin.cancel_order(
        chay['id'],
        'Mijoz fikrini o‘zgartirdi',
    )

    # 2) Delivery -> PAID -> CANCELLED
    delivery = admin.create_order({
        'order_type': 'DELIVERY',
        'delivery_worker_id': worker['id'],
        'items': [
            {
                'product_id': item['id'],
                'quantity': '2',
            }
        ],
    })

    admin.pay_order(delivery['id'])
    admin.cancel_order(
        delivery['id'],
        'Yetkazib berish bekor qilindi',
    )

    # 3) PAID, lekin CANCELLED emas -> endpointda chiqmasligi kerak
    paid = admin.create_order({
        'order_type': 'CHAYKHANA',
        'items': [
            {
                'product_id': item['id'],
                'quantity': '1',
            }
        ],
    })

    admin.pay_order(paid['id'])

    # 4) PENDING -> endpointda chiqmasligi kerak
    pending = admin.create_order({
        'order_type': 'DELIVERY',
        'delivery_worker_id': worker['id'],
        'items': [
            {
                'product_id': item['id'],
                'quantity': '1',
            }
        ],
    })

    business_date = get_current_business_date().isoformat()

    rows = admin.get(
        '/api/admin/reports/cancelled'
        f'?business_date={business_date}'
        '&period=kunlik'
    )

    ids = {row['id'] for row in rows}

    assert chay['id'] in ids
    assert delivery['id'] in ids
    assert paid['id'] not in ids
    assert pending['id'] not in ids

    chay_row = next(
        row for row in rows
        if row['id'] == chay['id']
    )

    assert chay_row['order_type'] == 'CHAYKHANA'
    assert chay_row['total_amount'] == 12000
    assert (
        chay_row['cancel_reason']
        == 'Mijoz fikrini o‘zgartirdi'
    )
    assert chay_row['cancelled_at'] is not None
    assert chay_row['cancelled_by']
    assert chay_row['delivery_worker'] is None

    delivery_row = next(
        row for row in rows
        if row['id'] == delivery['id']
    )

    assert delivery_row['order_type'] == 'DELIVERY'
    assert delivery_row['total_amount'] == 24000
    assert (
        delivery_row['cancel_reason']
        == 'Yetkazib berish bekor qilindi'
    )
    assert delivery_row['delivery_worker'] == worker['name']

    chay_only = admin.get(
        '/api/admin/reports/cancelled'
        f'?business_date={business_date}'
        '&period=kunlik'
        '&order_type=CHAYKHANA'
    )

    chay_ids = {row['id'] for row in chay_only}

    assert chay['id'] in chay_ids
    assert delivery['id'] not in chay_ids

    delivery_only = admin.get(
        '/api/admin/reports/cancelled'
        f'?business_date={business_date}'
        '&period=kunlik'
        '&order_type=DELIVERY'
    )

    delivery_ids = {row['id'] for row in delivery_only}

    assert delivery['id'] in delivery_ids
    assert chay['id'] not in delivery_ids
