from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote


JsonValue = dict[str, Any] | list[Any]


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class ApiAuthenticationError(ApiError):
    pass


class ApiConnectionError(Exception):
    pass


Transport = Callable[[Request, float], HttpResponse]


class PosApiClient:
    """Single HTTP boundary between the PySide application and FastAPI."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._transport = transport or self._urlopen_transport
        self.access_token: str | None = None
        self._images: dict[str, bytes] = {}

    def set_access_token(self, token: str) -> None:
        self.access_token = token

    def clear_session(self) -> None:
        self.access_token = None
        self._images.clear()

    @staticmethod
    def _urlopen_transport(request: Request, timeout_seconds: float) -> HttpResponse:
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - URL is terminal configuration.
                return HttpResponse(status_code=response.status, body=response.read())
        except HTTPError as error:
            return HttpResponse(status_code=error.code, body=error.read())
        except (URLError, OSError) as error:
            raise ApiConnectionError("POS serveriga ulanib bo‘lmadi") from error

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, *, raw_body: bytes | None = None) -> JsonValue:
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if raw_body is not None:
            data = raw_body
            headers['Content-Type'] = 'application/octet-stream'
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            response = self._transport(request, self.timeout_seconds)
        except ApiConnectionError:
            raise
        except (URLError, OSError) as error:
            raise ApiConnectionError("POS serveriga ulanib bo‘lmadi") from error

        try:
            decoded: JsonValue = json.loads(response.body.decode("utf-8")) if response.body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ApiError(response.status_code, "INVALID_RESPONSE", "Server noto‘g‘ri javob qaytardi") from error
        if not 200 <= response.status_code < 300:
            error_data = decoded.get("error", {}) if isinstance(decoded, dict) else {}
            code = str(error_data.get("code", "HTTP_ERROR"))
            message = str(error_data.get("message", "Server so‘rovni bajara olmadi"))
            error_type = ApiAuthenticationError if response.status_code == 401 else ApiError
            raise error_type(response.status_code, code, message)
        return decoded

    def get(self, path: str) -> JsonValue:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any] | None = None) -> JsonValue:
        return self.request("POST", path, payload)

    def login(self, username: str, password: str) -> dict[str, Any]:
        response = self.post("/api/auth/login", {"username": username, "password": password})
        assert isinstance(response, dict)
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise ApiError(200, "INVALID_RESPONSE", "Server access token qaytarmadi")
        self.set_access_token(token)
        return response

    def load_catalog(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        categories = self._all_pages("/api/categories")
        products = self._all_pages("/api/products")
        workers = self._all_pages("/api/delivery-workers")
        assert isinstance(categories, list) and isinstance(products, list) and isinstance(workers, list)
        return categories, products, workers

    def _all_pages(self, path):
        result = []
        while True:
            suffix = f"&offset={len(result)}" if result else ""
            separator = '&' if '?' in path else '?'
            page = self.get(f"{path}{separator}limit=100{suffix}")
            if not isinstance(page, list):
                raise ApiError(200, "INVALID_RESPONSE", "Katalog javobi noto‘g‘ri")
            result.extend(page)
            if len(page) < 100:
                return result

    def load_image(self, reference: str | None) -> bytes | None:
        if not reference:
            return None
        if reference in self._images:
            return self._images[reference]
        request = Request(f"{self.base_url}/api/product-images/{quote(reference, safe='/')}", headers={"Authorization": f"Bearer {self.access_token}"})
        try:
            response = self._transport(request, self.timeout_seconds)
            if response.status_code == 200:
                self._images[reference] = response.body
                return response.body
        except (ApiConnectionError, OSError, URLError):
            pass
        return None

    def get_order(self, order_id: int) -> dict[str, Any]:
        response = self.get(f"/api/orders/{order_id}")
        assert isinstance(response, dict)
        return response

    def list_orders(self, payment_status: str | None = None, offset: int = 0, limit: int = 30) -> list[dict[str, Any]]:
        from urllib.parse import urlencode
        params = {'limit': limit, 'offset': offset}
        if payment_status is not None:
            params['payment_status'] = payment_status
        response = self.get('/api/orders?' + urlencode(params))
        if not isinstance(response, list):
            raise ApiError(200, 'INVALID_RESPONSE', 'Buyurtmalar javobi noto‘g‘ri')
        return response

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.post("/api/orders", payload)
        assert isinstance(response, dict)
        return response

    def cancel_order(
        self,
        order_id: int,
        reason: str,
    ) -> dict[str, Any]:
        response = self.post(
            f"/api/orders/{order_id}/cancel",
            {"reason": reason},
        )
        return response

    def pay_order(self, order_id: int) -> dict[str, Any]:
        response = self.post(f"/api/orders/{order_id}/pay")
        assert isinstance(response, dict)
        return response

    def print_order(self, order_id: int, printer_id: int) -> dict[str, Any]:
        response = self.post(
            f"/api/orders/{order_id}/print",
            {"printer_id": printer_id},
        )
        assert isinstance(response, dict)
        return response

    def get_print_receipt(
        self,
        order_id: int,
    ) -> dict[str, Any]:
        response = self.get(
            f"/api/orders/{order_id}/receipt"
        )
        assert isinstance(response, dict)
        return response

    def report_local_print(
        self,
        order_id: int,
        printer_id: int,
        success: bool,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        response = self.post(
            f"/api/orders/{order_id}/local-print-result",
            {
                "printer_id": printer_id,
                "success": success,
                "error_message": error_message,
            },
        )
        assert isinstance(response, dict)
        return response
