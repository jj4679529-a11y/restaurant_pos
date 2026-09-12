from dataclasses import dataclass
from typing import Any

from app.ui.api_client import ApiConnectionError, ApiError, PosApiClient


@dataclass(frozen=True)
class CheckoutOutcome:
    payment: dict[str, Any]
    print_job: dict[str, Any] | None
    printer_configured: bool
    printed: bool
    print_error: str | None = None


def pay_and_print(client: PosApiClient, order_id: int, printer_id: int | None) -> CheckoutOutcome:
    """Payment is deliberately never reversed when subsequent printing fails."""
    payment = client.pay_order(order_id)
    return print_paid_order(client, order_id, printer_id, payment)


def print_paid_order(client: PosApiClient, order_id: int, printer_id: int | None, payment: dict) -> CheckoutOutcome:
    """Retry only printing, retaining the server-confirmed payment outcome."""
    if printer_id is None:
        return CheckoutOutcome(
            payment=payment,
            print_job=None,
            printer_configured=False,
            printed=False,
            print_error="Printer sozlanmagan",
        )
    try:
        print_job = client.print_order(order_id, printer_id)
    except (ApiError, ApiConnectionError) as error:
        return CheckoutOutcome(
            payment=payment,
            print_job=None,
            printer_configured=True,
            printed=False,
            print_error=str(error),
        )
    if print_job.get("status") == "SUCCESS":
        return CheckoutOutcome(payment=payment, print_job=print_job, printer_configured=True, printed=True)
    return CheckoutOutcome(
        payment=payment,
        print_job=print_job,
        printer_configured=True,
        printed=False,
        print_error=str(print_job.get("error_message") or "Chek chiqarilmadi"),
    )
