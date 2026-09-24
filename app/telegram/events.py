"""Project committed facts into the existing outbox, outside POS transactions."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, exists, func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import (BusinessDay, Order, OrderType, PaymentStatus, PrintJob,
                        PrintJobStatus, TelegramMessageType, TelegramOutbox, TelegramOutboxStatus)
from app.services.business_day_service import get_current_business_date, business_clock
from app.services.report_service import build_daily_report_data, DailyReportData, OrderTotals
from app.telegram.message_builder import (build_daily_report_message, build_delivery_assigned_message,
                                          build_printer_failure_message)

TASHKENT = ZoneInfo('Asia/Tashkent')


def enqueue(session, key, kind, text, order_id=None):
    session.execute(insert(TelegramOutbox).values(
        event_key=key, message_type=kind, message_text=text, order_id=order_id,
        status=TelegramOutboxStatus.PENDING, attempts=0,
    ).on_conflict_do_nothing(index_elements=['event_key']))


def collect_committed_events(session, batch_size=50):
    # Durable source rows allow recovery even after a crash between POS commit
    # and this scan. event_key prevents duplicate enqueue across worker restarts.
    jobs = session.scalars(select(PrintJob).join(Order).where(
        PrintJob.status == PrintJobStatus.ERROR, Order.payment_status == PaymentStatus.PAID,
        ~exists(select(TelegramOutbox.id).where(
            TelegramOutbox.event_key == 'print:' + cast(PrintJob.id, String))),
    ).order_by(PrintJob.id).limit(batch_size)).all()
    for job in jobs:
        enqueue(session, f'print:{job.id}', TelegramMessageType.PRINTER_FAILURE,
                build_printer_failure_message(job), job.order_id)
    orders = session.scalars(select(Order).where(
        Order.order_type == OrderType.DELIVERY,
        ~exists(select(TelegramOutbox.id).where(
            TelegramOutbox.event_key == 'delivery:' + cast(Order.id, String))),
    ).order_by(Order.id).limit(batch_size)).all()
    for order in orders:
        enqueue(session, f'delivery:{order.id}', TelegramMessageType.DELIVERY_ASSIGNED,
                build_delivery_assigned_message(order), order.id)


def current_report(session, now=None):
    business_date = get_current_business_date(now, session)
    day = session.scalar(select(BusinessDay).where(BusinessDay.business_date == business_date))
    if day is not None:
        return build_daily_report_data(session, day)
    zero = OrderTotals(0, 0)
    return DailyReportData(business_date, zero, zero, (), zero, zero, 0)


def schedule_report(session, report_time, now=None):
    if not report_time:
        return
    timezone, boundary = business_clock(session)
    now = (now or datetime.now(timezone)).astimezone(timezone)
    hour, minute = map(int, report_time.split(':'))
    # Before 06:00 belongs to the preceding business date. Compute that day's
    # scheduled wall clock instant, including schedules in the next morning.
    from datetime import timedelta
    business_date = get_current_business_date(now, session)
    scheduled_date = business_date + timedelta(days=1 if (hour, minute) < (boundary.hour, boundary.minute) else 0)
    due = datetime.combine(scheduled_date, datetime.min.time(), timezone).replace(hour=hour, minute=minute)
    if now < due:
        return
    key = f'scheduled-report:{business_date}'
    if session.scalar(select(TelegramOutbox.id).where(TelegramOutbox.event_key == key)):
        return
    report = current_report(session, now)
    enqueue(session, key, TelegramMessageType.DAILY_REPORT,
            build_daily_report_message(report) + '\n\nJoriy holat. Biznes kuni yopilmadi.')


def command_reply(session, command, now=None):
    help_text = (
        "🤖 Komronbek Zig'ir oshi admin bot\n\n"
        "Buyruqlar:\n"
        "/status — server va Telegram holati\n"
        "/today — bugungi savdo hisoboti\n"
        "/delivery — yetkazib berish hisoboti\n"
        "/help — buyruqlar ro‘yxati"
    )

    if command in ('/start', '/help'):
        return help_text

    if command == '/status':
        count = session.scalar(
            select(func.count())
            .select_from(TelegramOutbox)
            .where(
                TelegramOutbox.status
                != TelegramOutboxStatus.SENT
            )
        )

        business_date = get_current_business_date(
            now,
            session,
        )

        return "\n".join([
            "🟢 TIZIM HOLATI",
            "",
            "Backend: ishlayapti",
            f"Biznes kuni: {business_date.strftime('%d.%m.%Y')}",
            f"Telegram navbati: {count}",
        ])

    report = current_report(session, now)

    if command == '/today':
        return build_daily_report_message(report)

    if command == '/delivery':
        lines = [
            "🚚 YETKAZIB BERISH HISOBOTI",
            f"📅 {report.business_date.strftime('%d.%m.%Y')}",
            "",
            f"Buyurtmalar: {report.delivery.count} ta",
            (
                f"Jami: {report.delivery.amount:,} so‘m"
                .replace(",", " ")
            ),
        ]

        if report.delivery_workers:
            lines.extend([
                "",
                "Yetkazib beruvchilar:",
            ])

            lines.extend(
                (
                    f"{worker.worker_name} — "
                    f"{worker.count} ta / "
                    f"{worker.amount:,} so‘m"
                ).replace(",", " ")
                for worker in report.delivery_workers
            )
        else:
            lines.extend([
                "",
                "Bugun yetkazib berish yo‘q.",
            ])

        return "\n".join(lines)

    return help_text

