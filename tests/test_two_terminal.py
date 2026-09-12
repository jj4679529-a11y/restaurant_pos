"""Committed fixtures, independent HTTP clients and production request sessions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import date, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database.connection import SessionLocal
from app.models import (AddOn, BusinessDay, Category, DeliveryWorker, ManualPricePreset,
                        Order, OrderItem, OrderItemAddOn, Payment, PriceOption, Product,
                        ProductAddOn, PrintJob, TelegramOutbox, UnitType, User, UserRole)
from app.services import business_day_service
from main import app
from tests.auth_helpers import create_test_user


@pytest.fixture
def terminals(monkeypatch):
    suffix = uuid4().hex
    with SessionLocal() as db:
        day = date(2100, 1, 1) + timedelta(days=int(suffix[:6], 16) % 30000)
        while db.scalar(select(BusinessDay.id).where(BusinessDay.business_date == day)):
            day += timedelta(days=1)
        users = [create_test_user(db, name=f'Terminal {n}', username=f'wifi-{suffix}-{n}',
                                 role=UserRole.CASHIER if n < 2 else UserRole.ADMIN) for n in range(3)]
        category = Category(name=f'Wi-Fi fixture {suffix}')
        db.add(category)
        db.flush()
        product = Product(category_id=category.id, name=f'Wi-Fi fixture {suffix}',
                          unit_type=UnitType.PIECE, base_price=15000)
        db.add(product)
        db.flush()
        user_ids, usernames = [u.id for u in users], [u.username for u in users]
        category_id, product_id = category.id, product.id
        db.commit()
    # Isolate the date, not the business-day creation/locking implementation.
    monkeypatch.setattr(business_day_service, 'get_current_business_date', lambda now=None: day)
    assert not app.dependency_overrides
    try:
        with ExitStack() as stack:
            clients = [stack.enter_context(TestClient(app)) for _ in usernames]
            for client, username in zip(clients, usernames):
                login = client.post('/api/auth/login', json={'username': username, 'password': 'test-password'})
                assert login.status_code == 200, login.text
                client.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
            yield clients, product_id
    finally:
        with SessionLocal() as db:
            orders = select(Order.id).where(Order.created_by.in_(user_ids))
            items = select(OrderItem.id).where(OrderItem.order_id.in_(orders))
            db.execute(delete(OrderItemAddOn).where(OrderItemAddOn.order_item_id.in_(items)))
            for model in (PrintJob, TelegramOutbox, Payment, OrderItem):
                db.execute(delete(model).where(model.order_id.in_(orders)))
            db.execute(delete(Order).where(Order.created_by.in_(user_ids)))
            db.execute(delete(BusinessDay).where(BusinessDay.business_date == day))
            db.execute(delete(Product).where(Product.id == product_id))
            db.execute(delete(Category).where(Category.id == category_id))
            db.execute(delete(User).where(User.id.in_(user_ids)))
            db.commit()


def parallel(actions):
    barrier = Barrier(2, timeout=15)
    def run(action):
        barrier.wait()
        return action()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run, action) for action in actions]
        return [future.result(timeout=30) for future in futures]


@pytest.mark.parametrize('same_order', [False, True])
def test_two_clients_create_share_and_pay_concurrently(terminals, same_order):
    clients, product_id = terminals
    a, b = clients[:2]
    payload = {'order_type': 'CHAYKHANA', 'items': [{'product_id': product_id, 'quantity': '2.000'}]}
    responses = parallel([lambda: a.post('/api/orders', json=payload), lambda: b.post('/api/orders', json=payload)])
    for response in responses:
        assert response.status_code == 201, response.text
    orders = [r.json() for r in responses]
    assert len({o['order_number'] for o in orders}) == 2
    for client, order in zip((b, a), orders):
        assert order['total_amount'] == 30000 and order['payment_status'] == 'PENDING'
        listed = client.get('/api/orders', params={'payment_status': 'PENDING', 'limit': 100})
        assert listed.status_code == 200, listed.text
        assert order['id'] in [o['id'] for o in listed.json()]
        detail = client.get(f"/api/orders/{order['id']}")
        assert detail.status_code == 200 and detail.json()['total_amount'] == 30000
    ids = [orders[0]['id'], orders[0 if same_order else 1]['id']]
    paid = parallel([lambda: a.post(f'/api/orders/{ids[0]}/pay'), lambda: b.post(f'/api/orders/{ids[1]}/pay')])
    assert sorted(r.status_code for r in paid) == ([200, 409] if same_order else [200, 200])
    if same_order:
        assert next(r for r in paid if r.status_code == 409).json()['error']['code'] == 'ORDER_ALREADY_PAID'
    with SessionLocal() as db:
        for order_id in set(ids):
            assert db.get(Order, order_id).payment_status.value == 'PAID'
            payments = db.scalars(select(Payment).where(Payment.order_id == order_id)).all()
            events = db.scalars(select(TelegramOutbox).where(TelegramOutbox.order_id == order_id)).all()
            assert len(payments) == 1 and payments[0].amount == 30000
            assert len(events) == 1 and events[0].message_type.value == 'PAID_ORDER'
            assert events[0].status.value == 'PENDING'


def test_catalog_update_visible_to_both_sessions(terminals):
    clients, product_id = terminals
    for client in clients[:2]:
        assert client.get(f'/api/products/{product_id}').json()['base_price'] == 15000
    response = clients[2].patch(f'/api/products/{product_id}', json={'base_price': 19000})
    assert response.status_code == 200, response.text
    for client in clients[:2]:
        response = client.get('/api/products', params={'search': 'Wi-Fi fixture', 'limit': 100})
        assert response.status_code == 200, response.text
        assert next(p for p in response.json() if p['id'] == product_id)['base_price'] == 19000


def test_osh_addon_presets_and_worker_refresh_on_both_clients(terminals):
    clients, product_id = terminals
    admin = clients[2]
    # Only fixture-owned catalog records; never rename or price the real Osh.
    with SessionLocal() as db:
        db.get(Product, product_id).name = 'Osh'
        addon = AddOn(name=f'Wi-Fi manual {uuid4().hex}', unit_type=UnitType.AMOUNT,
                      base_price=0, allows_manual_price=True)
        worker = DeliveryWorker(name=f'Wi-Fi worker {uuid4().hex}', phone='fixture-phone')
        db.add_all([addon, worker])
        db.flush()
        addon_id, worker_id = addon.id, worker.id
        db.add(ProductAddOn(product_id=product_id, addon_id=addon_id))
        db.commit()
    try:
        updates = [
            admin.put(f'/api/admin/products/{product_id}/osh-prices', json={'half_price': 18000, 'full_price': 32000}),
            admin.patch(f'/api/addons/{addon_id}', json={'base_price': 7000}),
            admin.post('/api/manual-price-presets', json={'addon_id': addon_id, 'amount': 23000}),
            admin.patch(f'/api/delivery-workers/{worker_id}', json={'phone': 'fixture-updated'}),
        ]
        for response in updates:
            assert response.status_code in (200, 201), response.text
        for client in clients[:2]:
            response = client.get(f'/api/products/{product_id}')
            assert response.status_code == 200, response.text
            product = response.json()
            assert sorted(o['price'] for o in product['price_options'] if o['is_active']) == [18000, 32000]
            linked = next(a for a in product['available_addons'] if a['id'] == addon_id)
            assert linked['base_price'] == 7000 and linked['manual_price_presets'][0]['amount'] == 23000
            response = client.get('/api/delivery-workers', params={'limit': 100})
            assert response.status_code == 200, response.text
            assert next(w for w in response.json() if w['id'] == worker_id)['phone'] == 'fixture-updated'
    finally:
        with SessionLocal() as db:
            db.execute(delete(ManualPricePreset).where(ManualPricePreset.addon_id == addon_id))
            db.execute(delete(ProductAddOn).where(ProductAddOn.product_id == product_id))
            db.execute(delete(PriceOption).where(PriceOption.product_id == product_id))
            db.execute(delete(AddOn).where(AddOn.id == addon_id))
            db.execute(delete(DeliveryWorker).where(DeliveryWorker.id == worker_id))
            db.commit()
