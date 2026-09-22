import ctypes
import os
from ctypes import wintypes
from typing import Protocol

from app.models import Printer


class PrinterError(Exception):
    """A recoverable printer transport or hardware failure."""


class PrinterAdapter(Protocol):
    def print_receipt(self, printer: Printer, receipt: str) -> None: ...


class DOC_INFO_1(ctypes.Structure):
    _fields_ = [
        ("pDocName", wintypes.LPWSTR),
        ("pOutputFile", wintypes.LPWSTR),
        ("pDatatype", wintypes.LPWSTR),
    ]


class EscPosPrinter:
    """Send receipt text directly to the Windows RAW printer spooler."""

    def print_receipt(self, printer: Printer, receipt: str) -> None:
        if os.name != "nt":
            raise PrinterError(
                "Windows printer backend faqat Windows tizimida ishlaydi"
            )

        printer_name = (printer.address or "").strip()

        if not printer_name:
            raise PrinterError("Printer qurilma nomi kiritilmagan")

        # Printerga xavfsiz text.
        # Layoutdagi CRLF va bo'sh feed satrlar saqlanadi.
        text = (
            receipt
            .replace("‘", "'")
            .replace("’", "'")
            .replace("ʻ", "'")
            .replace("ʼ", "'")
            .replace("–", "-")
            .replace("—", "-")
        )

        # Har satr CRLF bo'lishini kafolatlaymiz.
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\n", "\r\n")

        # Thermal printer uchun pastki feed.
        if not text.endswith("\r\n\r\n\r\n\r\n\r\n\r\n"):
            text = text.rstrip("\r\n") + ("\r\n" * 6)

        try:
            raw = text.encode("ascii", errors="replace")

            winspool = ctypes.WinDLL(
                "winspool.drv",
                use_last_error=True,
            )

            OpenPrinterW = winspool.OpenPrinterW
            OpenPrinterW.argtypes = [
                wintypes.LPWSTR,
                ctypes.POINTER(wintypes.HANDLE),
                wintypes.LPVOID,
            ]
            OpenPrinterW.restype = wintypes.BOOL

            StartDocPrinterW = winspool.StartDocPrinterW
            StartDocPrinterW.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                ctypes.POINTER(DOC_INFO_1),
            ]
            StartDocPrinterW.restype = wintypes.DWORD

            StartPagePrinter = winspool.StartPagePrinter
            StartPagePrinter.argtypes = [wintypes.HANDLE]
            StartPagePrinter.restype = wintypes.BOOL

            WritePrinter = winspool.WritePrinter
            WritePrinter.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ]
            WritePrinter.restype = wintypes.BOOL

            EndPagePrinter = winspool.EndPagePrinter
            EndPagePrinter.argtypes = [wintypes.HANDLE]
            EndPagePrinter.restype = wintypes.BOOL

            EndDocPrinter = winspool.EndDocPrinter
            EndDocPrinter.argtypes = [wintypes.HANDLE]
            EndDocPrinter.restype = wintypes.BOOL

            ClosePrinter = winspool.ClosePrinter
            ClosePrinter.argtypes = [wintypes.HANDLE]
            ClosePrinter.restype = wintypes.BOOL

            handle = wintypes.HANDLE()

            if not OpenPrinterW(
                printer_name,
                ctypes.byref(handle),
                None,
            ):
                raise ctypes.WinError(
                    ctypes.get_last_error()
                )

            try:
                doc = DOC_INFO_1(
                    "Komronbek receipt",
                    None,
                    "RAW",
                )

                job_id = StartDocPrinterW(
                    handle,
                    1,
                    ctypes.byref(doc),
                )

                if not job_id:
                    raise ctypes.WinError(
                        ctypes.get_last_error()
                    )

                try:
                    if not StartPagePrinter(handle):
                        raise ctypes.WinError(
                            ctypes.get_last_error()
                        )

                    try:
                        written = wintypes.DWORD()

                        buffer = ctypes.create_string_buffer(raw)

                        if not WritePrinter(
                            handle,
                            buffer,
                            len(raw),
                            ctypes.byref(written),
                        ):
                            raise ctypes.WinError(
                                ctypes.get_last_error()
                            )

                        if written.value != len(raw):
                            raise PrinterError(
                                "Chek printerga to'liq yuborilmadi"
                            )

                    finally:
                        EndPagePrinter(handle)

                finally:
                    EndDocPrinter(handle)

            finally:
                ClosePrinter(handle)

        except PrinterError:
            raise
        except OSError as error:
            raise PrinterError(
                f"Windows printer xatosi: {error}"
            ) from error
