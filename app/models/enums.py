from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    CASHIER = "CASHIER"


class OrderType(StrEnum):
    CHAYKHANA = "CHAYKHANA"
    DELIVERY = "DELIVERY"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class BusinessDayStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PrintJobStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class TelegramOutboxStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    ERROR = "ERROR"


class UnitType(StrEnum):
    PORTION = "PORTION"
    PIECE = "PIECE"
    LITER = "LITER"
    AMOUNT = "AMOUNT"


class PrinterConnectionType(StrEnum):
    USB = "USB"
    NETWORK = "NETWORK"


class TelegramMessageType(StrEnum):
    PAID_ORDER = "PAID_ORDER"
    CANCELLED_ORDER = "CANCELLED_ORDER"
    DAILY_REPORT = "DAILY_REPORT"
    PRINTER_FAILURE = "PRINTER_FAILURE"
    DELIVERY_ASSIGNED = "DELIVERY_ASSIGNED"
    BOT_REPLY = "BOT_REPLY"
