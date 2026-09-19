import os
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from app.models import Printer


class PrinterError(Exception):
    """A recoverable printer transport or hardware failure."""


class PrinterAdapter(Protocol):
    def print_receipt(self, printer: Printer, receipt: str) -> None: ...


class EscPosPrinter:
    """Print receipts through the Windows printer spooler.

    The Printer.address field must contain the exact Windows printer name,
    for example: "Restaurant Receipt Printer".
    """

    def print_receipt(self, printer: Printer, receipt: str) -> None:
        if os.name != "nt":
            raise PrinterError("Windows printer backend faqat Windows tizimida ishlaydi")

        printer_name = (printer.address or "").strip()
        if not printer_name:
            raise PrinterError("Printer qurilma nomi kiritilmagan")

        receipt_text = receipt.rstrip() + "\r\n\r\n\r\n"

        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8-sig",
                suffix=".txt",
                delete=False,
                newline="",
            ) as temp_file:
                temp_file.write(receipt_text)
                temp_path = Path(temp_file.name)

            powershell_script = (
                "$ErrorActionPreference='Stop'; "
                "$text = Get-Content -LiteralPath $args[0] -Raw -Encoding UTF8; "
                "$text | Out-Printer -Name $args[1]"
            )

            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    powershell_script,
                    str(temp_path),
                    printer_name,
                ],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            if result.returncode != 0:
                error = (result.stderr or result.stdout or "").strip()
                raise PrinterError(
                    error or f"Printerga yuborib bo‘lmadi: {printer_name}"
                )

        except subprocess.TimeoutExpired as error:
            raise PrinterError("Printer javob bermadi") from error
        except OSError as error:
            raise PrinterError(f"Windows printer xatosi: {error}") from error
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
