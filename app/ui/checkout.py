from dataclasses import dataclass
from typing import Any

from app.ui.local_printer import (
    LocalPrinterError,
    print_receipt_by_name,
)
from app.ui.api_client import (
    ApiConnectionError,
    ApiError,
    PosApiClient,
)
from app.ui.config import UiSettings


@dataclass(frozen=True)
class CheckoutOutcome:
    payment: dict[str, Any]
    print_job: dict[str, Any] | None
    printer_configured: bool
    printed: bool
    print_error: str | None = None


def pay_and_print(
    client: PosApiClient,
    order_id: int,
    printer_id: int | None,
) -> CheckoutOutcome:
    """Payment is never reversed if printing later fails."""
    payment = client.pay_order(order_id)

    return print_paid_order(
        client,
        order_id,
        printer_id,
        payment,
    )


def print_paid_order(
    client: PosApiClient,
    order_id: int,
    printer_id: int | None,
    payment: dict,
) -> CheckoutOutcome:
    if printer_id is None:
        return CheckoutOutcome(
            payment=payment,
            print_job=None,
            printer_configured=False,
            printed=False,
            print_error="Printer sozlanmagan",
        )

    settings = UiSettings()
    local_printer = (
        settings.POS_LOCAL_PRINTER_NAME or ""
    ).strip()

    # New two-terminal mode:
    # every cashier terminal prints to its own
    # locally installed Windows printer.
    if local_printer:
        try:
            receipt_data = client.get_print_receipt(
                order_id
            )

            receipt = str(
                receipt_data.get("receipt") or ""
            )

            if not receipt:
                raise LocalPrinterError(
                    "Server chek matnini qaytarmadi"
                )

            print_receipt_by_name(
                local_printer,
                receipt,
            )

        except LocalPrinterError as error:
            try:
                print_job = client.report_local_print(
                    order_id,
                    printer_id,
                    False,
                    str(error),
                )
            except (ApiError, ApiConnectionError):
                print_job = None

            return CheckoutOutcome(
                payment=payment,
                print_job=print_job,
                printer_configured=True,
                printed=False,
                print_error=str(error),
            )

        except (ApiError, ApiConnectionError) as error:
            return CheckoutOutcome(
                payment=payment,
                print_job=None,
                printer_configured=True,
                printed=False,
                print_error=str(error),
            )

        try:
            print_job = client.report_local_print(
                order_id,
                printer_id,
                True,
                None,
            )
        except (ApiError, ApiConnectionError) as error:
            # Physical receipt already printed.
            # Do not claim printing itself failed.
            return CheckoutOutcome(
                payment=payment,
                print_job=None,
                printer_configured=True,
                printed=True,
                print_error=(
                    "Chek chiqdi, lekin print tarixi "
                    f"serverga yozilmadi: {error}"
                ),
            )

        return CheckoutOutcome(
            payment=payment,
            print_job=print_job,
            printer_configured=True,
            printed=True,
        )

    # Backward-compatible server-side printing.
    try:
        print_job = client.print_order(
            order_id,
            printer_id,
        )
    except (ApiError, ApiConnectionError) as error:
        return CheckoutOutcome(
            payment=payment,
            print_job=None,
            printer_configured=True,
            printed=False,
            print_error=str(error),
        )

    if print_job.get("status") == "SUCCESS":
        return CheckoutOutcome(
            payment=payment,
            print_job=print_job,
            printer_configured=True,
            printed=True,
        )

    return CheckoutOutcome(
        payment=payment,
        print_job=print_job,
        printer_configured=True,
        printed=False,
        print_error=str(
            print_job.get("error_message")
            or "Chek chiqarilmadi"
        ),
    )
