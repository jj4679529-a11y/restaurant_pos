"""Product report aggregates actual paid sales without a live database."""
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.telegram.events import product_report_message


@pytest.fixture
def sales():
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        for ddl in (
            'CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT)',
            'CREATE TABLE price_options (id INTEGER PRIMARY KEY, name TEXT)',
            'CREATE TABLE business_days (id INTEGER PRIMARY KEY, business_date DATE)',
            'CREATE TABLE orders (id INTEGER PRIMARY KEY, business_day_id INTEGER, payment_status TEXT)',
            'CREATE TABLE order_items (id INTEGER PRIMARY KEY, product_id INTEGER, order_id INTEGER, selected_price_option_id INTEGER, quantity NUMERIC, total_price INTEGER)',
        ):
            connection.execute(text(ddl))
        for sql in (
            "INSERT INTO products VALUES (1, 'Osh'), (2, 'Kompot'), (3, 'Osh')",
            "INSERT INTO price_options VALUES (1, '0.5 porsiya'), (2, '1 porsiya')",
            "INSERT INTO business_days VALUES (1, '2026-10-04'), (2, '2026-10-03')",
            "INSERT INTO orders VALUES (1, 1, 'PAID'), (2, 1, 'PENDING'), (3, 1, 'CANCELLED'), (4, 2, 'PAID')",
            # Stored totals include manual prices/add-ons; don't multiply today's catalog price.
            'INSERT INTO order_items VALUES (1,1,1,1,2,55000), (2,1,1,1,1,25000), (3,1,1,2,1,45000), (4,2,1,NULL,1.5,18000), (5,1,2,1,99,999999), (6,1,3,1,99,999999), (7,1,4,1,1,20000), (8,3,1,NULL,1,10000)',
        ):
            connection.execute(text(sql))
    with Session(engine) as session:
        yield session
    engine.dispose()


def report(session, start=date(2026, 10, 4), end=date(2026, 10, 4)):
    return product_report_message(session, start, end, 'Mahsulotlar')


def test_paid_product_quantities_and_actual_amounts(sales):
    message = report(sales)
    assert '• 0.5 porsiya — 3 ta / 80 000 so‘m' in message
    assert '• 1 porsiya — 1 ta / 45 000 so‘m' in message
    assert 'Jami: 4 ta / 125 000 so‘m' in message
    assert '• 1.5 ta / 18 000 so‘m' in message
    assert 'Umumiy summa: 153 000 so‘m' in message
    assert '999 999' not in message
    # Equal product names with distinct IDs remain separate.
    assert message.splitlines().count('Osh') == 2


def test_product_report_date_range(sales):
    message = report(sales, date(2026, 10, 3), date(2026, 10, 4))
    assert '• 0.5 porsiya — 4 ta / 100 000 so‘m' in message
    assert 'Umumiy summa: 173 000 so‘m' in message


def test_product_report_empty_period(sales):
    message = report(sales, date(2026, 10, 5), date(2026, 10, 5))
    assert 'Sotilgan mahsulot yo‘q.' in message
