"""Project committed facts into the existing outbox, outside POS transactions."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, exists, func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import (BusinessDay, DeliveryWorker, Order, OrderItem, Product, User, OrderType, PaymentStatus, PrintJob,
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
    args = args or []

    if command in ('/day', '/kun'):
        if not args:
            return (
                "Format:\n"
                "/kun 20.09.2026"
            )

        try:
            selected_date = datetime.strptime(
                args[0],
                "%d.%m.%Y",
            ).date()
        except ValueError:
            return (
                "❌ Sana formati noto‘g‘ri.\n"
                "Masalan: /kun 20.09.2026"
            )

        return period_report_message(
            session,
            selected_date,
            selected_date,
            "📊 KUNLIK HISOBOT",
        )

    if command in ('/month', '/oy'):
        if not args:
            return (
                "Format:\n"
                "/oy 09.2026"
            )

        try:
            month_date = datetime.strptime(
                args[0],
                "%m.%Y",
            ).date()
        except ValueError:
            return (
                "❌ Oy formati noto‘g‘ri.\n"
                "Masalan: /oy 09.2026"
            )

        month_start = month_date.replace(day=1)

        if month_start.month == 12:
            next_month = month_start.replace(
                year=month_start.year + 1,
                month=1,
            )
        else:
            next_month = month_start.replace(
                month=month_start.month + 1,
            )

        month_end = next_month - timedelta(days=1)

        return period_report_message(
            session,
            month_start,
            month_end,
            "📊 OYLIK HISOBOT",
        )

    if command in ('/week', '/hafta'):
        if not args:
            return (
                "Format:\n"
                "/hafta 21.09.2026"
            )

        try:
            selected_date = datetime.strptime(
                args[0],
                "%d.%m.%Y",
            ).date()
        except ValueError:
            return (
                "❌ Sana formati noto‘g‘ri.\n"
                "Masalan: /hafta 21.09.2026"
            )

        week_start = selected_date - timedelta(
            days=selected_date.weekday()
        )
        week_end = week_start + timedelta(days=6)

        return period_report_message(
            session,
            week_start,
            week_end,
            "📊 HAFTALIK HISOBOT",
        )

    business_date = get_current_business_date(
        now,
        session,
    )

    if command in ('/daily', '/kunlik'):
        return period_report_message(
            session,
            business_date,
            business_date,
            "📊 KUNLIK HISOBOT",
        )

    if command in ('/weekly', '/haftalik'):
        week_start = (
            business_date
            - timedelta(
                days=business_date.weekday()
            )
        )

        return period_report_message(
            session,
            week_start,
            business_date,
            "📊 HAFTALIK HISOBOT",
        )

    if command in ('/monthly', '/oylik'):
        month_start = business_date.replace(
            day=1
        )

        return period_report_message(
            session,
            month_start,
            business_date,
            "📊 OYLIK HISOBOT",
        )

    report = current_report(session, now)
    enqueue(session, key, TelegramMessageType.DAILY_REPORT,
            build_daily_report_message(report) + '\n\nJoriy holat. Biznes kuni yopilmadi.')



def period_report_message(session, start_date, end_date, title):
    day_ids = select(BusinessDay.id).where(
        BusinessDay.business_date >= start_date,
        BusinessDay.business_date <= end_date,
    )

    def totals(status, order_type=None):
        query = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
        ).where(
            Order.business_day_id.in_(day_ids),
            Order.payment_status == status,
        )

        if order_type is not None:
            query = query.where(Order.order_type == order_type)

        count, amount = session.execute(query).one()
        return int(count), int(amount)

    paid_count, paid_amount = totals(
        PaymentStatus.PAID
    )

    ch_count, ch_amount = totals(
        PaymentStatus.PAID,
        OrderType.CHAYKHANA,
    )

    del_count, del_amount = totals(
        PaymentStatus.PAID,
        OrderType.DELIVERY,
    )

    cancel_count, cancel_amount = totals(
        PaymentStatus.CANCELLED
    )

    pending_count, pending_amount = totals(
        PaymentStatus.PENDING
    )

    workers = session.execute(
        select(
            DeliveryWorker.name,
            func.count(Order.id),
            func.coalesce(
                func.sum(Order.total_amount),
                0,
            ),
        )
        .join(
            Order,
            Order.delivery_worker_id
            == DeliveryWorker.id,
        )
        .where(
            Order.business_day_id.in_(day_ids),
            Order.order_type == OrderType.DELIVERY,
            Order.payment_status
            == PaymentStatus.PAID,
        )
        .group_by(
            DeliveryWorker.id,
            DeliveryWorker.name,
        )
        .order_by(
            DeliveryWorker.name,
            DeliveryWorker.id,
        )
    ).all()

    lines = [
        title,
        (
            f"📅 {start_date.strftime('%d.%m.%Y')}"
            if start_date == end_date
            else (
                f"📅 {start_date.strftime('%d.%m.%Y')}"
                f" — {end_date.strftime('%d.%m.%Y')}"
            )
        ),
        "",
        "💰 JAMI SAVDO",
        f"Buyurtmalar: {paid_count} ta",
        (
            f"Summa: {paid_amount:,} so‘m"
            .replace(",", " ")
        ),
        "",
        "🍽 CHOYXONA",
        f"Buyurtmalar: {ch_count} ta",
        (
            f"Summa: {ch_amount:,} so‘m"
            .replace(",", " ")
        ),
        "",
        "🚚 YETKAZIB BERISH",
        f"Buyurtmalar: {del_count} ta",
        (
            f"Summa: {del_amount:,} so‘m"
            .replace(",", " ")
        ),
    ]

    if workers:
        lines.extend([
            "",
            "Yetkazib beruvchilar:",
        ])

        for name, count, amount in workers:
            lines.append(
                (
                    f"{name} — "
                    f"{int(count)} ta / "
                    f"{int(amount):,} so‘m"
                ).replace(",", " ")
            )

    lines.extend([
        "",
        "❌ BEKOR QILINGAN",
        (
            f"{cancel_count} ta / "
            f"{cancel_amount:,} so‘m"
        ).replace(",", " "),
        "",
        "⏳ KUTILAYOTGAN",
        (
            f"{pending_count} ta / "
            f"{pending_amount:,} so‘m"
        ).replace(",", " "),
    ])

    return "\n".join(lines)


def command_reply(session, command, now=None, args=None):
    help_text = (
        "🤖 Komronbek Zig'ir oshi — boshqaruv boti\n\n"

        "📊 HISOBOTLAR\n"
        "/bugun — bugungi to‘liq hisobot\n"
        "/kunlik — joriy kun hisoboti\n"
        "/haftalik — joriy hafta hisoboti\n"
        "/oylik — joriy oy hisoboti\n\n"

        "📅 TARIXIY HISOBOTLAR\n"
        "/kun DD.MM.YYYY — tanlangan kun\n"
        "/hafta DD.MM.YYYY — tanlangan hafta\n"
        "/oy MM.YYYY — tanlangan oy\n\n"

        "🧾 BUYURTMALAR\n"
        "/buyurtmalar — oxirgi buyurtmalar\n"
        "/kutilayotgan — kutilayotgan buyurtmalar\n"
        "/bekor — bekor qilingan buyurtmalar\n\n"

        "🚚 YETKAZIB BERISH\n"
        "/yetkazish — bugungi yetkazib berish hisoboti\n"
        "/yetkazuvchilar — yetkazib beruvchilar kesimi\n\n"

        "👥 SAVDO TAHLILI\n"
        "/kassirlar — kassirlar kesimi\n"
        "/topmahsulotlar — eng ko‘p sotilgan mahsulotlar\n\n"

        "⚙️ TIZIM\n"
        "/holat — server va Telegram holati\n"
        "/yordam — buyruqlar ro‘yxati"
    )

    if command in ('/start', '/help', '/boshlash', '/yordam'):
        return help_text

    if command in ('/status', '/holat'):
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

    if command in ('/today', '/bugun'):
        return build_daily_report_message(report)

    if command in ('/orders', '/buyurtmalar'):
        business_date = get_current_business_date(
            now,
            session,
        )

        day = session.scalar(
            select(BusinessDay).where(
                BusinessDay.business_date == business_date
            )
        )

        if day is None:
            return (
                "🧾 OXIRGI BUYURTMALAR\n"
                f"📅 {business_date.strftime('%d.%m.%Y')}\n\n"
                "Bugun buyurtmalar yo‘q."
            )

        rows = session.execute(
            select(
                Order.order_number,
                Order.created_at,
                Order.order_type,
                Order.total_amount,
                Order.payment_status,
                DeliveryWorker.name,
            )
            .outerjoin(
                DeliveryWorker,
                DeliveryWorker.id == Order.delivery_worker_id,
            )
            .where(
                Order.business_day_id == day.id
            )
            .order_by(
                Order.created_at.desc(),
                Order.id.desc(),
            )
            .limit(10)
        ).all()

        if not rows:
            return (
                "🧾 OXIRGI BUYURTMALAR\n"
                f"📅 {business_date.strftime('%d.%m.%Y')}\n\n"
                "Bugun buyurtmalar yo‘q."
            )

        lines = [
            "🧾 OXIRGI BUYURTMALAR",
            f"📅 {business_date.strftime('%d.%m.%Y')}",
            "",
        ]

        for row in rows:
            created_at = row.created_at

            if created_at.tzinfo is None:
                created_at = created_at.replace(
                    tzinfo=TASHKENT
                )

            local_time = created_at.astimezone(
                TASHKENT
            )

            if row.order_type is OrderType.DELIVERY:
                order_type = "Yetkazib berish"
                if row.name:
                    order_type += f" — {row.name}"
            else:
                order_type = "Choyxona"

            status_value = (
                row.payment_status.value
                if hasattr(row.payment_status, "value")
                else str(row.payment_status)
            )

            status_text = {
                "PAID": "✅ To‘langan",
                "PENDING": "⏳ Kutilmoqda",
                "CANCELLED": "❌ Bekor qilingan",
            }.get(
                status_value,
                status_value,
            )

            lines.extend([
                f"#{row.order_number}",
                f"Sana: {local_time.strftime('%d.%m.%Y')}",
                f"Vaqt: {local_time.strftime('%H:%M')}",
                f"Turi: {order_type}",
                (
                    f"Jami: {row.total_amount:,} so‘m"
                    .replace(",", " ")
                ),
                f"Holat: {status_text}",
                "",
            ])

        return "\n".join(lines).rstrip()

    if command in ('/cancelled', '/bekor'):
        business_date = get_current_business_date(
            now,
            session,
        )

        day = session.scalar(
            select(BusinessDay).where(
                BusinessDay.business_date == business_date
            )
        )

        if day is None:
            return (
                "❌ BEKOR QILINGAN BUYURTMALAR\n"
                f"📅 {business_date.strftime('%d.%m.%Y')}\n\n"
                "Bugun bekor qilingan buyurtma yo‘q."
            )

        rows = session.execute(
            select(
                Order.order_number,
                Order.cancelled_at,
                Order.created_at,
                Order.order_type,
                Order.total_amount,
                Order.cancel_reason,
                DeliveryWorker.name,
            )
            .outerjoin(
                DeliveryWorker,
                DeliveryWorker.id == Order.delivery_worker_id,
            )
            .where(
                Order.business_day_id == day.id,
                Order.payment_status == PaymentStatus.CANCELLED,
            )
            .order_by(
                Order.cancelled_at.desc(),
                Order.id.desc(),
            )
            .limit(20)
        ).all()

        if not rows:
            return (
                "❌ BEKOR QILINGAN BUYURTMALAR\n"
                f"📅 {business_date.strftime('%d.%m.%Y')}\n\n"
                "Bugun bekor qilingan buyurtma yo‘q."
            )

        lines = [
            "❌ BEKOR QILINGAN BUYURTMALAR",
            f"📅 {business_date.strftime('%d.%m.%Y')}",
            "",
        ]

        total_cancelled = 0

        for row in rows:
            event_time = row.cancelled_at or row.created_at

            if event_time.tzinfo is None:
                event_time = event_time.replace(
                    tzinfo=TASHKENT
                )

            local_time = event_time.astimezone(
                TASHKENT
            )

            if row.order_type is OrderType.DELIVERY:
                order_type = "Yetkazib berish"
                if row.name:
                    order_type += f" — {row.name}"
            else:
                order_type = "Choyxona"

            total_cancelled += row.total_amount

            lines.extend([
                f"#{row.order_number}",
                f"Sana: {local_time.strftime('%d.%m.%Y')}",
                f"Vaqt: {local_time.strftime('%H:%M')}",
                f"Turi: {order_type}",
                (
                    f"Summa: {row.total_amount:,} so‘m"
                    .replace(",", " ")
                ),
                f"Sabab: {row.cancel_reason or 'Ko‘rsatilmagan'}",
                "",
            ])

        lines.extend([
            f"Bekor qilinganlar: {len(rows)} ta",
            (
                f"Jami summa: {total_cancelled:,} so‘m"
                .replace(",", " ")
            ),
        ])

        return "\n".join(lines).rstrip()

    if command in ('/pending', '/kutilayotgan'):
        business_date = get_current_business_date(now, session)

        day = session.scalar(
            select(BusinessDay).where(
                BusinessDay.business_date == business_date
            )
        )

        if day is None:
            return "⏳ KUTILAYOTGAN BUYURTMALAR\n\nBugun buyurtmalar yo‘q."

        rows = session.execute(
            select(
                Order.order_number,
                Order.created_at,
                Order.order_type,
                Order.total_amount,
                DeliveryWorker.name,
            )
            .outerjoin(
                DeliveryWorker,
                DeliveryWorker.id == Order.delivery_worker_id,
            )
            .where(
                Order.business_day_id == day.id,
                Order.payment_status == PaymentStatus.PENDING,
            )
            .order_by(
                Order.created_at.desc(),
                Order.id.desc(),
            )
            .limit(20)
        ).all()

        if not rows:
            return (
                "⏳ KUTILAYOTGAN BUYURTMALAR\n"
                f"📅 {business_date.strftime('%d.%m.%Y')}\n\n"
                "Kutilayotgan buyurtma yo‘q."
            )

        lines = [
            "⏳ KUTILAYOTGAN BUYURTMALAR",
            f"📅 {business_date.strftime('%d.%m.%Y')}",
            "",
        ]

        for row in rows:
            created_at = row.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=TASHKENT)

            local = created_at.astimezone(TASHKENT)

            order_type = (
                f"Yetkazib berish — {row.name}"
                if row.order_type is OrderType.DELIVERY and row.name
                else (
                    "Yetkazib berish"
                    if row.order_type is OrderType.DELIVERY
                    else "Choyxona"
                )
            )

            lines.extend([
                f"#{row.order_number}",
                f"Sana: {local.strftime('%d.%m.%Y')}",
                f"Vaqt: {local.strftime('%H:%M')}",
                f"Turi: {order_type}",
                f"Jami: {row.total_amount:,} so‘m".replace(",", " "),
                "",
            ])

        return "\n".join(lines).rstrip()

    if command in ('/cashiers', '/kassirlar'):
        business_date = get_current_business_date(now, session)

        day = session.scalar(
            select(BusinessDay).where(
                BusinessDay.business_date == business_date
            )
        )

        if day is None:
            return "👤 KASSIRLAR\n\nBugun savdo yo‘q."

        rows = session.execute(
            select(
                User.name,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_amount), 0),
            )
            .join(Order, Order.created_by == User.id)
            .where(
                Order.business_day_id == day.id,
                Order.payment_status == PaymentStatus.PAID,
            )
            .group_by(User.id, User.name)
            .order_by(
                func.sum(Order.total_amount).desc(),
                User.name,
            )
        ).all()

        lines = [
            "👤 KASSIRLAR HISOBOTI",
            f"📅 {business_date.strftime('%d.%m.%Y')}",
            "",
        ]

        if not rows:
            lines.append("Bugun savdo yo‘q.")
        else:
            for name, count, amount in rows:
                lines.append(
                    f"{name} — {int(count)} ta / {int(amount):,} so‘m"
                    .replace(",", " ")
                )

        return "\n".join(lines)

    if command in ('/workers', '/yetkazuvchilar'):
        business_date = get_current_business_date(now, session)

        day = session.scalar(
            select(BusinessDay).where(
                BusinessDay.business_date == business_date
            )
        )

        if day is None:
            return "🚚 YETKAZIB BERUVCHILAR\n\nBugun yetkazib berish yo‘q."

        rows = session.execute(
            select(
                DeliveryWorker.name,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total_amount), 0),
            )
            .join(
                Order,
                Order.delivery_worker_id == DeliveryWorker.id,
            )
            .where(
                Order.business_day_id == day.id,
                Order.order_type == OrderType.DELIVERY,
                Order.payment_status == PaymentStatus.PAID,
            )
            .group_by(
                DeliveryWorker.id,
                DeliveryWorker.name,
            )
            .order_by(
                func.sum(Order.total_amount).desc(),
                DeliveryWorker.name,
            )
        ).all()

        lines = [
            "🚚 YETKAZIB BERUVCHILAR",
            f"📅 {business_date.strftime('%d.%m.%Y')}",
            "",
        ]

        if not rows:
            lines.append("Bugun yetkazib berish yo‘q.")
        else:
            for name, count, amount in rows:
                lines.append(
                    f"{name} — {int(count)} ta / {int(amount):,} so‘m"
                    .replace(",", " ")
                )

        return "\n".join(lines)

    if command in ('/top', '/topmahsulotlar'):
        business_date = get_current_business_date(now, session)

        day = session.scalar(
            select(BusinessDay).where(
                BusinessDay.business_date == business_date
            )
        )

        if day is None:
            return "🏆 TOP MAHSULOTLAR\n\nBugun savdo yo‘q."

        rows = session.execute(
            select(
                Product.name,
                func.coalesce(func.sum(OrderItem.quantity), 0),
                func.coalesce(func.sum(OrderItem.total_price), 0),
            )
            .join(
                OrderItem,
                OrderItem.product_id == Product.id,
            )
            .join(
                Order,
                Order.id == OrderItem.order_id,
            )
            .where(
                Order.business_day_id == day.id,
                Order.payment_status == PaymentStatus.PAID,
            )
            .group_by(
                Product.id,
                Product.name,
            )
            .order_by(
                func.sum(OrderItem.quantity).desc(),
                func.sum(OrderItem.total_price).desc(),
            )
            .limit(10)
        ).all()

        lines = [
            "🏆 TOP MAHSULOTLAR",
            f"📅 {business_date.strftime('%d.%m.%Y')}",
            "",
        ]

        if not rows:
            lines.append("Bugun savdo yo‘q.")
        else:
            for index, (name, quantity, amount) in enumerate(rows, 1):
                lines.append(
                    (
                        f"{index}. {name} — "
                        f"{quantity:g} ta / "
                        f"{int(amount):,} so‘m"
                    ).replace(",", " ")
                )

        return "\n".join(lines)

    if command in ('/delivery', '/yetkazish'):
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

