from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import Category, Setting
from tests.auth_helpers import admin_headers, create_test_user
from main import app


def test_catalog_api_end_to_end(db: Session) -> None:
    suffix = uuid4().hex[:8]
    category = Category(name=f"API Category {suffix}", sort_order=99, is_active=True)
    db.add_all([category, Setting(key=f"api_setting_{suffix}", value="initial")])
    db.flush()
    admin = create_test_user(db, name="Catalog Admin", username=f"catalog-admin-{suffix}")

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app, headers=admin_headers(admin)) as client:
            listed = client.get("/api/categories")
            assert listed.status_code == 200

            duplicate = client.post("/api/categories", json={"name": category.name, "sort_order": 1})
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "conflict"

            product = client.post("/api/products", json={
                "category_id": category.id, "name": f"API Product {suffix}", "unit_type": "PORTION", "base_price": 10000,
            })
            assert product.status_code == 201
            product_id = product.json()["id"]

            option = client.post(f"/api/products/{product_id}/price-options", json={"name": "10000", "quantity": "1.000", "price": 10000})
            assert option.status_code == 201
            assert client.post(f"/api/products/{product_id}/price-options", json={"name": "duplicate", "quantity": "1", "price": 10000}).status_code == 409
            assert client.post(f"/api/products/{product_id}/price-options", json={"name": "bad", "quantity": "1", "price": 0}).status_code == 422
            assert client.post("/api/products/999999/price-options", json={"name": "missing", "quantity": "1", "price": 1}).status_code == 404

            gosht = client.post("/api/addons", json={
                "name": f"Go'sht API {suffix}", "unit_type": "AMOUNT", "base_price": 0, "allows_manual_price": True,
            })
            assert gosht.status_code == 201
            assert gosht.json()["allows_manual_price"] is True
            addon_id = gosht.json()["id"]
            assert client.post(f"/api/products/{product_id}/addons/{addon_id}").status_code == 201
            assert client.post(f"/api/products/{product_id}/addons/{addon_id}").status_code == 409
            assert client.post(f"/api/products/999999/addons/{addon_id}").status_code == 404

            detail = client.get(f"/api/products/{product_id}")
            assert detail.status_code == 200
            assert [item["price"] for item in detail.json()["price_options"]] == [10000]
            assert detail.json()["available_addons"][0]["allows_manual_price"] is True

            worker = client.post("/api/delivery-workers", json={"name": f"Worker {suffix}", "phone": f"api-{suffix}"})
            assert worker.status_code == 201
            assert client.patch(f"/api/delivery-workers/{worker.json()['id']}", json={"is_active": False}).status_code == 200
            assert all(item["id"] != worker.json()["id"] for item in client.get("/api/delivery-workers").json())

            settings = client.get("/api/settings")
            assert settings.status_code == 200
            assert all("PASSWORD" not in item["key"].upper() and "DATABASE" not in item["key"].upper() for item in settings.json())
            assert client.patch(f"/api/settings/api_setting_{suffix}", json={"value": "updated"}).json()["value"] == "updated"
    finally:
        app.dependency_overrides.clear()
