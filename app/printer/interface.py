from typing import Protocol

from app.models import Printer


class PrinterError(Exception):
    """A recoverable printer transport or hardware failure."""


class PrinterAdapter(Protocol):
    def print_receipt(self, printer: Printer, receipt: str) -> None: ...


class EscPosPrinter:
    """Hardware adapter boundary for a future ESC/POS backend.

    No ESC/POS dependency is installed in the application yet.  Returning a
    recoverable error is safer than pretending a receipt was physically printed.
    Tests replace this adapter through dependency injection.
    """

    def print_receipt(self, printer: Printer, receipt: str) -> None:
        raise PrinterError("ESC/POS printer backend is not configured")
