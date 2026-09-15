from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BusinessDay, BusinessDayStatus, TelegramMessageType, TelegramOutbox, TelegramOutboxStatus, Setting
from app.services.errors import ServiceError
from app.services.report_service import DailyReportData, build_daily_report_data
from app.telegram.message_builder import build_daily_report_message

TASHKENT = ZoneInfo("Asia/Tashkent")
BUSINESS_DAY_START = time(6, 0)


@dataclass(frozen=True)
class ClosePreviousBusinessDayResult:
    previous_day: BusinessDay | None
    current_day: BusinessDay
    report: DailyReportData | None
    report_created: bool


def business_clock(session=None):
    values = dict(session.execute(select(Setting.key, Setting.value).where(
        Setting.key.in_(['timezone', 'business_day_start']))).all()) if session is not None else {}
    return ZoneInfo(values.get('timezone', 'Asia/Tashkent')), time.fromisoformat(values.get('business_day_start', '06:00'))


def _now(now: datetime | None = None, session=None) -> datetime:
    timezone, _ = business_clock(session)
    if now is None:
        return datetime.now(timezone)
    if now.tzinfo is None:
        raise ValueError("Business-day time must be timezone-aware")
    return now.astimezone(timezone)


def get_current_business_date(now: datetime | None = None, session=None) -> date:
    local_now = _now(now, session)
    _, boundary = business_clock(session)
    return local_now.date() if local_now.timetz().replace(tzinfo=None) >= boundary else local_now.date() - timedelta(days=1)


def get_or_create_current_business_day(session: Session, now: datetime | None = None) -> BusinessDay:
    business_date = get_current_business_date(now, session)
    current = session.scalars(select(BusinessDay).where(BusinessDay.business_date == business_date)).one_or_none()
    if current is not None:
        return current

    local_now = _now(now, session)
    timezone, boundary = business_clock(session)
    started_at = datetime.combine(business_date, boundary, tzinfo=timezone)
    day = BusinessDay(business_date=business_date, started_at=started_at, status=BusinessDayStatus.OPEN)
    try:
        with session.begin_nested():
            session.add(day)
            session.flush()
    except IntegrityError:
        day = session.scalars(select(BusinessDay).where(BusinessDay.business_date == business_date)).one()
    return day


def ensure_open_business_day(session: Session, now: datetime | None = None) -> BusinessDay:
    day = get_or_create_current_business_day(session, now)
    if day.status is not BusinessDayStatus.OPEN:
        raise ServiceError(409, "business_day_closed", "The current business day is closed")
    return day


def close_previous_business_day(
    session: Session,
    now: datetime | None = None,
) -> ClosePreviousBusinessDayResult:
    """Close the completed business day and enqueue its immutable daily report.

    The caller owns the surrounding transaction.  In particular, this function
    neither commits nor rolls back, so the day state and outbox message are
    persisted atomically by the caller.  Orders retain the business day given
    at creation; a later payment for an old pending order does not alter this
    snapshot or enqueue a report adjustment in this MVP.
    """
    local_now = _now(now, session)
    _, boundary = business_clock(session)
    if local_now.timetz().replace(tzinfo=None) < boundary:
        raise ServiceError(
            409,
            "business_day_close_not_available",
            "The previous business day can be closed at or after 06:00 Asia/Tashkent",
        )

    current_day = ensure_open_business_day(session, local_now)
    previous_date = current_day.business_date - timedelta(days=1)
    previous_day = session.scalars(
        select(BusinessDay)
        .where(BusinessDay.business_date == previous_date)
        .with_for_update()
    ).one_or_none()

    if previous_day is None or previous_day.status is BusinessDayStatus.CLOSED:
        return ClosePreviousBusinessDayResult(
            previous_day=previous_day,
            current_day=current_day,
            report=None,
            report_created=False,
        )

    report = build_daily_report_data(session, previous_day)
    previous_day.status = BusinessDayStatus.CLOSED
    previous_day.closed_at = local_now
    session.add(
        TelegramOutbox(
            message_type=TelegramMessageType.DAILY_REPORT,
            order_id=None,
            message_text=build_daily_report_message(report),
            status=TelegramOutboxStatus.PENDING,
            attempts=0,
        )
    )
    session.flush()
    return ClosePreviousBusinessDayResult(
        previous_day=previous_day,
        current_day=current_day,
        report=report,
        report_created=True,
    )


def close_business_day(session: Session, now: datetime | None = None) -> BusinessDay:
    day = get_or_create_current_business_day(session, now)
    if day.status is BusinessDayStatus.CLOSED:
        raise ServiceError(409, "business_day_closed", "The current business day is already closed")
    day.status = BusinessDayStatus.CLOSED
    day.closed_at = _now(now, session)
    session.commit()
    session.refresh(day)
    return day
