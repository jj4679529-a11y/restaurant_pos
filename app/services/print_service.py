from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderItem, OrderItemAddOn, PrintJob, PrintJobStatus, Printer, Setting
from app.printer.interface import PrinterAdapter, PrinterError
from app.printer.receipt_builder import build_receipt
from app.services.errors import ServiceError

TASHKENT = ZoneInfo("Asia/Tashkent")


@dataclass(frozen=True)
class PrintResult:
    job: PrintJob


def _order(session: Session, order_id: int) -> Order:
    order = session.scalars(
        select(Order)
        .where(Order.id == order_id)
        .options(
            selectinload(Order.delivery_worker),
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.addons).selectinload(OrderItemAddOn.addon),
        )
    ).one_or_none()
    if order is None:
        raise ServiceError(404, "ORDER_NOT_FOUND", "Order not found")
    return order


def _printer(session: Session, printer_id: int) -> Printer:
    printer = session.get(Printer, printer_id)
    if printer is None:
        raise ServiceError(404, "PRINTER_NOT_FOUND", "Printer not found")
    if not printer.is_active:
        raise ServiceError(400, "PRINTER_INACTIVE", "Printer is inactive")
    return printer


def _restaurant_name(session: Session) -> str:
    setting = session.scalars(select(Setting).where(Setting.key == "restaurant_name")).one_or_none()
    if setting is None or not setting.value.strip():
        raise ServiceError(409, "RESTAURANT_NAME_NOT_CONFIGURED", "Restaurant name is not configured")
    return setting.value


def print_order(session: Session, order_id: int, printer_id: int, adapter: PrinterAdapter) -> PrintResult:
    """Create one persisted print attempt in the caller-owned transaction."""
    order = _order(session, order_id)
    printer = _printer(session, printer_id)
    receipt = build_receipt(order, _restaurant_name(session))
    job = PrintJob(
        order_id=order.id,
        printer_id=printer.id,
        status=PrintJobStatus.PENDING,
        attempted_at=datetime.now(TASHKENT),
    )
    session.add(job)
    session.flush()
    try:
        adapter.print_receipt(printer, receipt)
    except PrinterError as error:
        job.status = PrintJobStatus.ERROR
        job.error_message = str(error)
    else:
        job.status = PrintJobStatus.SUCCESS
        job.printed_at = datetime.now(TASHKENT)
    return PrintResult(job=job)


def retry_print_job(session: Session, print_job_id: int, adapter: PrinterAdapter) -> PrintResult:
    previous = session.get(PrintJob, print_job_id)
    if previous is None:
        raise ServiceError(404, "PRINT_JOB_NOT_FOUND", "Print job not found")
    if previous.status is not PrintJobStatus.ERROR:
        raise ServiceError(409, "PRINT_JOB_NOT_RETRYABLE", "Only failed print jobs can be retried")
    # Preserve the failed job and create a distinct historical attempt.
    return print_order(session, previous.order_id, previous.printer_id, adapter)
