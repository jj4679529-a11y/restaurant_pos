from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CashierOrAdminUser, DbSession
from app.printer.interface import EscPosPrinter, PrinterAdapter
from app.schemas.printing import PrintJobResponse, PrintOrderRequest
from app.services import print_service

router = APIRouter(tags=["printing"])


def get_printer_adapter() -> PrinterAdapter:
    return EscPosPrinter()


PrinterAdapterDep = Annotated[PrinterAdapter, Depends(get_printer_adapter)]


def _response(job) -> dict:
    return {
        "print_job_id": job.id,
        "order_id": job.order_id,
        "printer_id": job.printer_id,
        "status": job.status,
        "attempted_at": job.attempted_at,
        "printed_at": job.printed_at,
        "error_message": job.error_message,
    }


@router.post("/orders/{order_id}/print", response_model=PrintJobResponse)
def print_order(order_id: int, data: PrintOrderRequest, db: DbSession, adapter: PrinterAdapterDep, _user: CashierOrAdminUser):
    try:
        result = print_service.print_order(db, order_id, data.printer_id, adapter)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _response(result.job)


@router.post("/print-jobs/{print_job_id}/retry", response_model=PrintJobResponse)
def retry_print_job(print_job_id: int, db: DbSession, adapter: PrinterAdapterDep, _user: CashierOrAdminUser):
    try:
        result = print_service.retry_print_job(db, print_job_id, adapter)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _response(result.job)
