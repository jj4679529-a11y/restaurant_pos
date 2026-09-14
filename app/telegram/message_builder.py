from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import Order, OrderType
from app.services.report_service import DailyReportData

TASHKENT = ZoneInfo("Asia/Tashkent")


def _format_money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so‘m"


def build_paid_order_message(order: Order, cashier_name: str = "Noma’lum") -> str:
    paid_at = order.paid_at or datetime.now(TASHKENT)
    local_time = paid_at.astimezone(TASHKENT).strftime("%H:%M")
    lines = [
        "✅ TO'LOV QABUL QILINDI",
        "",
        f"Buyurtma: #{order.order_number}",
        f"Kassir: {cashier_name}",
        f"Turi: {'Choyxona' if order.order_type is OrderType.CHAYKHANA else 'Yetkazib berish'}",
        f"Jami: {_format_money(order.total_amount)}",
        f"Vaqt: {local_time}",
    ]
    if order.order_type is OrderType.DELIVERY and order.delivery_worker is not None:
        lines.append(f"Yetkazib beruvchi: {order.delivery_worker.name}")
    return "\n".join(lines)


def build_cancelled_order_message(order: Order) -> str:
    cancelled_at = order.cancelled_at or datetime.now(TASHKENT)
    local_time = cancelled_at.astimezone(TASHKENT).strftime("%H:%M")
    lines = [
        "❌ BUYURTMA BEKOR QILINDI",
        "",
        f"Buyurtma: #{order.order_number}",
        f"Mijoz: {'Choyxonada' if order.order_type is OrderType.CHAYKHANA else 'Yetkazib berish'}",
        f"Summa: {_format_money(order.total_amount)}",
        f"Sabab: {order.cancel_reason}",
        f"Bekor qilgan: {order.canceller.name if order.canceller is not None else 'Noma’lum'}",
        f"Vaqt: {local_time}",
    ]
    if order.order_type is OrderType.DELIVERY and order.delivery_worker is not None:
        lines.append(f"Yetkazib beruvchi: {order.delivery_worker.name}")
    return "\n".join(lines)


def build_daily_report_message(report: DailyReportData) -> str:
    lines = [
        "📊 KUNLIK HISOBOT",
        f"📅 {report.business_date.strftime('%d.%m.%Y')}",
        f"Sana: {report.business_date.isoformat()}",
        f"Jami savdo: {_format_money(report.overall.amount)}",
        f"Buyurtmalar: {report.overall.count}",
        "",
        "Choyxonada:",
        f"Buyurtmalar: {report.chaykhana.count}",
        f"Summa: {_format_money(report.chaykhana.amount)}",
        "",
        "Yetkazib berish:",
        f"Buyurtmalar: {report.delivery.count}",
        f"Summa: {_format_money(report.delivery.amount)}",
    ]
    if report.delivery_workers:
        lines.extend(["", "Yetkazib beruvchilar:"])
        lines.extend(
            f"{worker.worker_name} — {worker.count} ta / {_format_money(worker.amount)}"
            for worker in report.delivery_workers
        )
    lines.extend([
        "",
        "Jami:",
        f"{report.overall.count} ta buyurtma",
        _format_money(report.overall.amount),
        "",
        "Bekor qilingan:",
        f"{report.cancelled.count} ta / {_format_money(report.cancelled.amount)}",
        "",
        "Kutilayotgan:",
        f"{report.pending_count} ta",
    ])
    if report.cashiers:
        lines.extend(["", "Kassirlar:"])
        lines.extend(f"{name} — {_format_money(amount)}" for name, amount in report.cashiers)
    return "\n".join(lines)


def build_printer_failure_message(job) -> str:
    return "\n".join([
        "⚠️ CHEK CHIQMADI", "", f"Buyurtma: #{job.order.order_number}",
        "To'lov qabul qilindi: HA", f"Jami: {_format_money(job.order.total_amount)}",
        f"Printer: {job.printer.name}",
        "Xato: Printerga ulanish yoki chop etish xatosi. Printerni tekshiring.",
    ])  # Never forward adapter exceptions, URLs, stack traces, or credentials.


def build_delivery_assigned_message(order) -> str:
    return "\n".join([
        "🚚 YETKAZIB BERISH TAYINLANDI", f"Buyurtma: #{order.order_number}",
        f"Yetkazib beruvchi: {order.delivery_worker.name}",
        f"Jami: {_format_money(order.total_amount)}",
    ])
