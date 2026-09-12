import json
from urllib.request import Request

import pytest

from app.ui.api_client import (
    ApiAuthenticationError,
    ApiConnectionError,
    HttpResponse,
    PosApiClient,
)


class FakeTransport:
    def __init__(self, responses: list[HttpResponse]) -> None:
        self.responses = responses
        self.requests: list[Request] = []

    def __call__(self, request: Request, _timeout: float) -> HttpResponse:
        self.requests.append(request)
        return self.responses.pop(0)


def _response(status_code: int, body: object) -> HttpResponse:
    return HttpResponse(status_code=status_code, body=json.dumps(body).encode("utf-8"))


def test_login_stores_runtime_token_and_uses_bearer_header() -> None:
    transport = FakeTransport([
        _response(200, {"access_token": "runtime-token", "token_type": "bearer", "user": {"id": 7}}),
        _response(200, []),
    ])
    client = PosApiClient("http://pos.local:8000", transport=transport)

    response = client.login("cashier", "password")
    client.get("/api/categories")

    assert response["user"]["id"] == 7
    assert client.access_token == "runtime-token"
    assert transport.requests[0].full_url == "http://pos.local:8000/api/auth/login"
    assert transport.requests[1].get_header("Authorization") == "Bearer runtime-token"


def test_login_failure_and_connection_failure_are_explicit() -> None:
    rejected = PosApiClient(
        "http://pos.local:8000",
        transport=FakeTransport([_response(401, {"error": {"code": "INVALID_CREDENTIALS", "message": "bad"}})]),
    )
    with pytest.raises(ApiAuthenticationError) as error:
        rejected.login("cashier", "wrong")
    assert error.value.code == "INVALID_CREDENTIALS"

    def unavailable(_request: Request, _timeout: float) -> HttpResponse:
        raise OSError("offline")

    offline = PosApiClient("http://pos.local:8000", transport=unavailable)
    with pytest.raises(ApiConnectionError):
        offline.get("/api/categories")


def test_catalog_loading_uses_authenticated_existing_endpoints() -> None:
    transport = FakeTransport([
        _response(200, [{"id": 1, "name": "Osh"}]),
        _response(200, [{"id": 9, "name": "Osh", "price_options": [], "available_addons": []}]),
        _response(200, [{"id": 3, "name": "Ali"}]),
    ])
    client = PosApiClient("http://pos.local:8000", transport=transport)
    client.set_access_token("runtime-token")

    categories, products, workers = client.load_catalog()

    assert categories[0]["name"] == "Osh"
    assert products[0]["id"] == 9
    assert workers[0]["name"] == "Ali"
    assert [request.full_url for request in transport.requests] == [
        "http://pos.local:8000/api/categories?limit=100",
        "http://pos.local:8000/api/products?limit=100",
        "http://pos.local:8000/api/delivery-workers?limit=100",
    ]


def test_catalog_pagination_does_not_drop_products() -> None:
    transport = FakeTransport([
        _response(200, []),
        _response(200, [{"id": n} for n in range(100)]),
        _response(200, [{"id": 100}]),
        _response(200, []),
    ])
    client = PosApiClient("http://pos.local:8000", transport=transport)
    _, products, _ = client.load_catalog()
    assert len(products) == 101
    assert transport.requests[2].full_url.endswith("/api/products?limit=100&offset=100")


def test_images_use_local_authenticated_endpoint_cache_and_fallback() -> None:
    transport = FakeTransport([HttpResponse(200, b"image"), HttpResponse(404, b"")])
    client = PosApiClient("http://pos.local:8000", transport=transport)
    client.set_access_token("runtime-token")
    assert client.load_image("menu/food photo.png") == b"image"
    assert client.load_image("menu/food photo.png") == b"image"
    assert len(transport.requests) == 1
    assert transport.requests[0].full_url.endswith("/api/product-images/menu/food%20photo.png")
    assert transport.requests[0].get_header("Authorization") == "Bearer runtime-token"
    assert client.load_image("missing.png") is None
    assert client.load_image(None) is None
    client.clear_session()
    assert not client._images and client.access_token is None


def test_order_listing_uses_existing_status_filter_and_auth():
    transport = FakeTransport([_response(200, [{'id': 9}])])
    client = PosApiClient('http://pos.local:8000', transport=transport)
    client.set_access_token('runtime-token')
    assert client.list_orders('PENDING', offset=30) == [{'id': 9}]
    assert transport.requests[0].full_url.endswith('/api/orders?limit=30&offset=30&payment_status=PENDING')
    assert transport.requests[0].get_header('Authorization') == 'Bearer runtime-token'
