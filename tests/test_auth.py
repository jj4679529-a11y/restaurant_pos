from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.printing import get_printer_adapter
from app.core.security import create_access_token, verify_password
from app.database.connection import get_db
from app.models import (
    Category,
    Order,
    Payment,
    Printer,
    PrinterConnectionType,
    Product,
    Setting,
    UnitType,
    User,
    UserRole,
)
from main import app
from tests.auth_helpers import admin_headers, auth_headers, cashier_headers, create_test_user


class FakePrinter:
    def print_receipt(self, _printer: Printer, _receipt: str) -> None:
        pass


def test_login_returns_role_limited_user_and_rejects_invalid_credentials(db: Session) -> None:
    suffix = uuid4().hex[:8]
    admin = create_test_user(
        db,
        name="Administrator",
        username=f"auth-admin-{suffix}",
        password="admin-password",
    )
    cashier = create_test_user(
        db,
        name="Cashier",
        username=f"auth-cashier-{suffix}",
        password="cashier-password",
        role=UserRole.CASHIER,
    )
    inactive = create_test_user(
        db,
        name="Inactive",
        username=f"auth-inactive-{suffix}",
        password="inactive-password",
        is_active=False,
    )
    legacy_blank_password_admin = create_test_user(
        db,
        name="Legacy Admin",
        username=f"auth-legacy-{suffix}",
        password="",
    )
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            admin_login = client.post(
                "/api/auth/login",
                json={"username": admin.username, "password": "admin-password"},
            )
            assert admin_login.status_code == 200, admin_login.text
            admin_body = admin_login.json()
            assert admin_body["token_type"] == "bearer"
            assert admin_body["access_token"]
            assert admin_body["user"] == {
                "id": admin.id,
                "name": "Administrator",
                "username": admin.username,
                "role": "ADMIN",
            }
            assert "password_hash" not in admin_login.text

            cashier_login = client.post(
                "/api/auth/login",
                json={"username": cashier.username, "password": "cashier-password"},
            )
            assert cashier_login.status_code == 200, cashier_login.text
            assert cashier_login.json()["user"]["role"] == "CASHIER"

            legacy_login = client.post(
                "/api/auth/login",
                json={"username": legacy_blank_password_admin.username, "password": ""},
            )
            assert legacy_login.status_code == 200, legacy_login.text

            wrong_password = client.post(
                "/api/auth/login",
                json={"username": admin.username, "password": "wrong"},
            )
            assert wrong_password.status_code == 401
            assert wrong_password.json()["error"]["code"] == "INVALID_CREDENTIALS"

            unknown_user = client.post(
                "/api/auth/login",
                json={"username": "does-not-exist", "password": "wrong"},
            )
            assert unknown_user.status_code == 401
            assert unknown_user.json()["error"]["code"] == "INVALID_CREDENTIALS"

            inactive_login = client.post(
                "/api/auth/login",
                json={"username": inactive.username, "password": "inactive-password"},
            )
            assert inactive_login.status_code == 403
            assert inactive_login.json()["error"]["code"] == "USER_INACTIVE"
    finally:
        app.dependency_overrides.clear()


def test_token_failures_and_db_user_state_are_enforced(db: Session) -> None:
    user = create_test_user(db, name="Token Cashier", username=f"token-{uuid4().hex[:8]}", role=UserRole.CASHIER)
    expired_token = create_access_token(user, now=datetime.now(timezone.utc) - timedelta(minutes=721))
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            missing = client.get("/api/products")
            assert missing.status_code == 401
            assert missing.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

            malformed = client.get("/api/products", headers={"Authorization": "Bearer not-a-token"})
            assert malformed.status_code == 401
            assert malformed.json()["error"]["code"] == "INVALID_TOKEN"

            expired = client.get("/api/products", headers={"Authorization": f"Bearer {expired_token}"})
            assert expired.status_code == 401
            assert expired.json()["error"]["code"] == "TOKEN_EXPIRED"

            valid_headers = cashier_headers(user)
            assert client.get("/api/products", headers=valid_headers).status_code == 200
            user.is_active = False
            db.flush()
            inactive = client.get("/api/products", headers=valid_headers)
            assert inactive.status_code == 403
            assert inactive.json()["error"]["code"] == "USER_INACTIVE"
    finally:
        app.dependency_overrides.clear()


def test_catalog_and_settings_permissions(db: Session) -> None:
    suffix = uuid4().hex[:8]
    admin = create_test_user(db, name="Catalog Admin", username=f"catalog-admin-{suffix}")
    cashier = create_test_user(
        db,
        name="Catalog Cashier",
        username=f"catalog-cashier-{suffix}",
        role=UserRole.CASHIER,
    )
    setting = Setting(key=f"auth-setting-{suffix}", value="before")
    db.add(setting)
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/categories",
                headers=admin_headers(admin),
                json={"name": f"Admin category {suffix}"},
            )
            assert created.status_code == 201, created.text
            updated_setting = client.patch(
                f"/api/settings/{setting.key}",
                headers=admin_headers(admin),
                json={"value": "after"},
            )
            assert updated_setting.status_code == 200, updated_setting.text

            assert client.get("/api/categories", headers=cashier_headers(cashier)).status_code == 200
            denied_catalog_write = client.post(
                "/api/categories",
                headers=cashier_headers(cashier),
                json={"name": f"Cashier category {suffix}"},
            )
            assert denied_catalog_write.status_code == 403
            assert denied_catalog_write.json()["error"]["code"] == "FORBIDDEN"
            denied_settings = client.patch(
                f"/api/settings/{setting.key}",
                headers=cashier_headers(cashier),
                json={"value": "cashier"},
            )
            assert denied_settings.status_code == 403
            assert denied_settings.json()["error"]["code"] == "FORBIDDEN"
    finally:
        app.dependency_overrides.clear()


def test_admin_user_management_hashes_password_and_prevents_self_deactivation(db: Session) -> None:
    suffix = uuid4().hex[:8]
    admin = create_test_user(db, name="Users Admin", username=f"users-admin-{suffix}")
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/users",
                headers=admin_headers(admin),
                json={
                    "name": "Kassir 1",
                    "username": f"cashier-{suffix}",
                    "password": "first-password",
                    "role": "CASHIER",
                },
            )
            assert created.status_code == 201, created.text
            created_body = created.json()
            assert created_body["role"] == "CASHIER"
            assert "password_hash" not in created.text
            cashier_id = created_body["id"]
            cashier = db.get(User, cashier_id)
            assert cashier is not None and verify_password("first-password", cashier.password_hash)

            blank_password = client.post(
                "/api/users",
                headers=admin_headers(admin),
                json={
                    "name": "Blank password",
                    "username": f"blank-password-{suffix}",
                    "password": "   ",
                    "role": "CASHIER",
                },
            )
            assert blank_password.status_code == 422

            listed = client.get("/api/users", headers=admin_headers(admin))
            assert listed.status_code == 200
            assert all("password_hash" not in item for item in listed.json())

            replaced = client.patch(
                f"/api/users/{cashier_id}",
                headers=admin_headers(admin),
                json={"password": "replacement-password", "name": "Kassir Yangilangan"},
            )
            assert replaced.status_code == 200, replaced.text
            assert verify_password("replacement-password", db.get(User, cashier_id).password_hash)

            duplicate = client.post(
                "/api/users",
                headers=admin_headers(admin),
                json={
                    "name": "Duplicate",
                    "username": f"cashier-{suffix}",
                    "password": "password",
                    "role": "CASHIER",
                },
            )
            assert duplicate.status_code == 409

            cashier_headers_value = auth_headers(db.get(User, cashier_id))
            cashier_cannot_create = client.post(
                "/api/users",
                headers=cashier_headers_value,
                json={"name": "No", "username": f"no-{suffix}", "password": "password", "role": "CASHIER"},
            )
            assert cashier_cannot_create.status_code == 403
            assert cashier_cannot_create.json()["error"]["code"] == "FORBIDDEN"

            self_deactivation = client.patch(
                f"/api/users/{admin.id}",
                headers=admin_headers(admin),
                json={"is_active": False},
            )
            assert self_deactivation.status_code == 409
            assert self_deactivation.json()["error"]["code"] == "CANNOT_DEACTIVATE_CURRENT_USER"

            deactivated = client.patch(
                f"/api/users/{cashier_id}",
                headers=admin_headers(admin),
                json={"is_active": False},
            )
            assert deactivated.status_code == 200
            assert deactivated.json()["is_active"] is False
    finally:
        app.dependency_overrides.clear()


def test_cashier_is_the_order_payment_and_cancellation_actor_and_can_print(db: Session) -> None:
    suffix = uuid4().hex[:8]
    cashier = create_test_user(
        db,
        name="Actor Cashier",
        username=f"actor-cashier-{suffix}",
        role=UserRole.CASHIER,
    )
    category = Category(name=f"Actor category {suffix}", sort_order=1, is_active=True)
    product = Product(
        category=category,
        name=f"Actor product {suffix}",
        unit_type=UnitType.PIECE,
        base_price=15_000,
        allows_manual_price=False,
        is_active=True,
    )
    printer = Printer(
        name=f"Actor printer {suffix}",
        terminal_name=f"actor-{suffix}",
        connection_type=PrinterConnectionType.NETWORK,
        address="127.0.0.1:9100",
        is_active=True,
    )
    db.add_all([category, product, printer])
    if db.scalars(select(Setting).where(Setting.key == "restaurant_name")).one_or_none() is None:
        db.add(Setting(key="restaurant_name", value="Test Restaurant"))
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_printer_adapter] = FakePrinter
    headers = cashier_headers(cashier)
    payload = {
        "order_type": "CHAYKHANA",
        "created_by": 999_999,
        "items": [{"product_id": product.id, "quantity": "1"}],
    }
    try:
        with TestClient(app) as client:
            unauthenticated = client.post("/api/orders", json=payload)
            assert unauthenticated.status_code == 401
            assert unauthenticated.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

            created = client.post("/api/orders", headers=headers, json=payload)
            assert created.status_code == 201, created.text
            order_id = created.json()["id"]
            order = db.get(Order, order_id)
            assert order is not None and order.created_by == cashier.id

            paid = client.post(f"/api/orders/{order_id}/pay", headers=headers)
            assert paid.status_code == 200, paid.text
            payment = db.scalars(select(Payment).where(Payment.order_id == order_id)).one()
            assert payment.created_by == cashier.id

            printed = client.post(
                f"/api/orders/{order_id}/print",
                headers=headers,
                json={"printer_id": printer.id},
            )
            assert printed.status_code == 200, printed.text

            second = client.post("/api/orders", headers=headers, json=payload)
            assert second.status_code == 201, second.text
            cancelled = client.post(
                f"/api/orders/{second.json()['id']}/cancel",
                headers=headers,
                json={"reason": "Mijoz ketdi"},
            )
            assert cancelled.status_code == 200, cancelled.text
            assert db.get(Order, second.json()["id"]).cancelled_by == cashier.id
    finally:
        app.dependency_overrides.clear()
